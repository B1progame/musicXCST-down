FIRST_RUN_NOTICE = (
    "Use this tool only for music or audio you own, have permission to use, "
    "or are legally allowed to download."
)


def can_download(confirmed: bool) -> bool:
    return bool(confirmed)
