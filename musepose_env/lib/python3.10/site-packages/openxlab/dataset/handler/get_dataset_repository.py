"""
get dataset repository totally
"""

import os
import sys
from typing import Tuple

from rich import print as rprint

from openxlab.dataset.commands.utility import ContextInfoNoLogin
from openxlab.dataset.constants import FILE_THRESHOLD
from openxlab.dataset.io import downloader
from openxlab.dataset.utils import bytes2human
from openxlab.dataset.utils import calculate_file_sha256
from openxlab.dataset.utils import format_progress_string
from openxlab.xlab.handler.user_token import trigger_update_check


def get(dataset_repo: str, target_path=""):
    """
    Get the dataset repository.

    Example:
        openxlab.dataset.get(
            dataset_repo="username/dataset_repo_name",
            target_path="/path/to/local/folder"
        )

    Parameters:
        @dataset_repo String The address of dataset repository.
        @target_path String The target local path to save the dataset repository.
    """
    # update check
    trigger_update_check()

    if not target_path:
        target_path = os.getcwd()
    if target_path.startswith('~'):
        target_path = os.path.expanduser(target_path)
    target_path = os.path.realpath(target_path)

    ctx = ContextInfoNoLogin()
    client = ctx.get_client()

    # parse dataset_name
    parsed_ds_name = dataset_repo.replace("/", ",")
    parsed_save_path = dataset_repo.replace("/", "___")

    rprint("Fetching the list of datasets...")
    data_dict = client.get_api().get_dataset_files(dataset_name=parsed_ds_name, needContent=True)
    info_dataset_id = data_dict['list'][0]['dataset_id']

    object_info_list = []
    for info in data_dict['list']:
        curr_dict = {}
        curr_dict['size'] = info['size']
        curr_dict['name'] = info['path'][1:]
        curr_dict['sha256'] = info['sha256']
        object_info_list.append(curr_dict)

    if object_info_list:
        # download check for crawler with one file
        download_check_path = object_info_list[0]['name']
        # download check
        client.get_api().download_check(dataset_id=info_dataset_id, path=download_check_path)
        obj, local_file_path = process_download_files(
            client, object_info_list, target_path, parsed_save_path, info_dataset_id
        )
    client.get_api().track_download_dataset_files(dataset_name=parsed_ds_name, file_path="")
    rprint("Download Completed.")
    rprint(f"The {obj} has been successfully downloaded to {local_file_path}")


def process_download_files(
    client, object_info_list, target_path, parsed_save_path, info_dataset_id
) -> Tuple[str, str]:
    # obtain num of files to download
    total_files = len(object_info_list)
    total_size = sum(file['size'] for file in object_info_list)
    finished_size = 0

    rprint(f"Downloading {len(object_info_list)} files: ")

    for idx in range(len(object_info_list)):
        file_size = object_info_list[idx]['size']
        file_name = object_info_list[idx]['name']
        file_path = os.path.join(target_path, parsed_save_path, file_name)

        # update downloaded files size and progress
        finished_size += file_size
        progress = round((finished_size / total_size) * 100)
        msg = format_progress_string(progress, idx, total_files, finished_size, total_size)

        # file exist already
        if os.path.exists(file_path):
            # calculate file sha256
            file_sha256 = calculate_file_sha256(file_path=file_path)
            if file_sha256 == object_info_list[idx]['sha256']:
                if idx >= 1:
                    # clear msg in terminal of total progress
                    print("\033[2K\r", end="")
                rprint(f"{idx+1}. {file_path} already exists, jumping to next!")
                rprint(msg, end="")

                # the final msg of total progress
                if idx + 1 == total_files:
                    print("\033[2K\r", end="")
                    rprint(msg)
                    break

                continue

        # big file download
        if file_size > FILE_THRESHOLD:
            # add a new line to print progress of big file
            sys.stdout.write("\n")
            download_url = client.get_api().get_dataset_download_urls(
                info_dataset_id, object_info_list[idx]
            )
            downloader.BigFileDownloader(
                url=download_url,
                filename=file_name,
                idx=idx,
                download_dir=os.path.join(target_path, parsed_save_path),
                file_size=file_size,
                blocks_num=8,
            ).start()
            # clear msgs before two lines in terminal of total progress and progress of big file
            print("\033[1A\033[2K\033[1B\033[2K\033[1A\r", end="")

        # small file download
        else:
            download_url = client.get_api().get_dataset_download_urls(
                info_dataset_id, object_info_list[idx]
            )
            downloader.SmallFileDownload(
                url=download_url,
                filename=file_name,
                download_dir=os.path.join(target_path, parsed_save_path),
            )._single_thread_download()

            # clear the output of total downloaded progress in terminal if file idx != 1
            if idx >= 1:
                print("\033[2K\r", end="")

        # print progress msg of every new downloaded files
        rprint(
            f"{idx+1}. file: {file_name}, size: {bytes2human(file_size,format='%(value).2f%(symbol)s')}, progress: 100%"
        )

        # the final new download file needs a new line
        if idx + 1 == total_files:
            # print with “\n”
            rprint(msg)
        else:
            # print without “\n”
            rprint(msg, end="")
    # obtain the download path of file or folder
    if len(object_info_list) == 1:
        return 'file', file_path
    else:
        return 'folder', os.path.dirname(file_path)
