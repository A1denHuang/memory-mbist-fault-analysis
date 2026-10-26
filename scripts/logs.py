"""Portable public logs: retain diagnostics without recording machine paths."""
from pathlib import Path
import re


def public_log(text, root=None):
    if root is not None:
        root = Path(root).resolve()
        for prefix in (str(root), root.as_posix()):
            text = re.sub(re.escape(prefix) + r'[\\/]?', '', text, flags=re.I)
    # Source references from simulators may point at an older checkout.
    text = re.sub(r'[A-Za-z]:[\\/][^\r\n"\']*?[\\/](?=(?:rtl|tb|scripts|results(?:_questa)?)[\\/])', '', text)
    text = re.sub(r'/' + r'home/[^\s"\']*?/(?=(?:rtl|tb|scripts|results(?:_questa)?)/)', '', text)
    # Tool installation paths add no diagnostic value; keep the tool filename.
    text = re.sub(r'[A-Za-z]:[\\/][^\s"\']*[\\/]([^\\/\s"\']+)', r'<tool>/\1', text)
    return text
