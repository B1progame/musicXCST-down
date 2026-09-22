FIRST_RUN_NOTICE = (
    "Use this tool only for music, audio, or video you own, have permission to use, "
    "or are legally allowed to download. You alone are responsible for what "
    "you download; B1progame and MusicXCST Downloader are not responsible for "
    "downloads of music, audio, or video you do not own or have rights to use."
)


def can_download(confirmed: bool) -> bool:
    return bool(confirmed)
