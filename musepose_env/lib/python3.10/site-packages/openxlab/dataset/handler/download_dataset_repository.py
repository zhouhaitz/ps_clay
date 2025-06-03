"""
download specific file/files according to source_path(single file/relative path) of dataset repository
"""
import os
import re

from rich import print as rprint

from openxlab.dataset.commands.utility import ContextInfoNoLogin
from openxlab.dataset.handler.get_dataset_repository import process_download_files
from openxlab.xlab.handler.user_token import trigger_update_check


def download(dataset_repo: str, source_path: str, target_path=""):
    """
    Download file or folder of a dataset repository.

    Example:
        openxlab.dataset.download(
            dataset_repo="username/dataset_repo_name",
            source_path="/raw/file",
            target_path="/path/to/local/folder"
        )

    Parameters:
        @dataset_repo String The address of dataset repository.
        @source_path String The relative path of the target file or folder to download.
        @target_path String The target local path to store the file or folder.
    """
    # update check
    trigger_update_check()

    if not target_path:
        target_path = os.getcwd()
    if target_path.startswith('~'):
        target_path = os.path.expanduser(target_path)
    target_path = os.path.realpath(target_path)

    # remove prefix of . in soure_path
    source_path = re.sub(r'^\.+', '', source_path)

    ctx = ContextInfoNoLogin()
    client = ctx.get_client()

    # parse dataset_name
    parsed_ds_name = dataset_repo.replace("/", ",")
    # huggingface use underscores when loading/downloading datasets
    parsed_save_path = dataset_repo.replace("/", "___")

    rprint("Fetching the list of files...")
    get_payload = {"prefix": source_path}
    data_dict = client.get_api().get_dataset_files(
        dataset_name=parsed_ds_name, payload=get_payload, needContent=True
    )
    info_dataset_id = data_dict['list'][0]['dataset_id']

    object_info_list = []
    for info in data_dict['list']:
        curr_dict = {}
        curr_dict['size'] = info['size']
        curr_dict['name'] = info['path'][1:]
        curr_dict['sha256'] = info['sha256']
        # without destination path upload file,file has prefix with '//'
        if info['path'].startswith('//'):
            curr_dict['name'] = info['path'][2:]
        object_info_list.append(curr_dict)

    if object_info_list:
        # download check for crawler with one file
        download_check_path = object_info_list[0]['name']
        # download check
        client.get_api().download_check(dataset_id=info_dataset_id, path=download_check_path)
        obj, local_file_path = process_download_files(
            client, object_info_list, target_path, parsed_save_path, info_dataset_id
        )

    client.get_api().track_download_dataset_files(
        dataset_name=parsed_ds_name, file_path=source_path
    )
    rprint("Download Completed.")
    rprint(f"The {obj} has been successfully downloaded to {local_file_path}")
