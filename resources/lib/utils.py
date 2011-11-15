import socket
import xbmc
import xbmcgui
import xbmcaddon
import platform


"""
This module contains helper classes and functions to assist in the
operation of script.extrafanartdownloader
"""

### get addon info
__addon__ = xbmcaddon.Addon('script.artwork.downloader')
__addonid__ = __addon__.getAddonInfo('id')
__addonname__ = __addon__.getAddonInfo('name')
__addonversion__ = __addon__.getAddonInfo('version')
__icon__ = __addon__.getAddonInfo('icon')
__localize__ = __addon__.getLocalizedString


dialog = xbmcgui.DialogProgress()

timeout = 20
socket.setdefaulttimeout(timeout)

def _log(txt, severity=xbmc.LOGDEBUG):

    """Log to txt xbmc.log at specified severity"""
    try:
        message = 'script.artwork.downloader: %s' % txt
        xbmc.log(msg=message, level=severity)
    except:
        xbmc.log('ASCII character error')


def _dialog(action, percentage = 0, line1 = '', line2 = '', line3 = '', background = False):
    if not background:
        if action == 'create':
            dialog.create(__addonname__, line1)
        if action == 'update':
            dialog.update(percentage, line1, line2, line3)
        if action == 'close':
            dialog.close()
        if action == 'iscanceled':
            if dialog.iscanceled():
                return True
            else:
                return False
        if action == 'okdialog':
            xbmcgui.Dialog().ok(__addonname__, line1, line2)
    if background:
        if (action == 'create' or action == 'okdialog'):
            if line2 == '':
                msg = line1
            else:
                msg = line1 + ': ' + line2
            xbmc.executebuiltin("XBMC.Notification(%s, %s, 7500, %s)" % (__addonname__, msg, __icon__))
