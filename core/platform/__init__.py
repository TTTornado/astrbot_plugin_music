from .apple import AppleMusic
from .base import BaseMusicPlayer
from .hgovo import HgovoMusic
from .kugou import KuGouMusic
from .kugou_api import KuGouMusicAPI
from .kuwo import KuwoMusic
from .neko import NekoMusic
from .netease import NetEaseMusic
from .netease_api import NetEaseMusicAPI
from .qqmusic import QQMusic
from .soda import SodaMusic
from .txqq import TXQQMusic
from .xunhuisi import XunhuisiMusic

__all__ = [
    "BaseMusicPlayer",
    "HgovoMusic",
    "NetEaseMusic",
    "NetEaseMusicAPI",
    "QQMusic",
    "KuGouMusicAPI",
    "KuGouMusic",
    "KuwoMusic",
    "TXQQMusic",
    "NekoMusic",
    "AppleMusic",
    "SodaMusic",
    "XunhuisiMusic",
]
