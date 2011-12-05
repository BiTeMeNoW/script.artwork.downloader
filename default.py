﻿### import
import re
import os
import time
import sys
import xbmc
import xbmcaddon
import platform
import xbmcgui
import urllib
from traceback import print_exc

### import libraries
from resources.lib import media_setup
from resources.lib import provider
from resources.lib.utils import _log as log
from resources.lib.utils import _dialog as dialog
from resources.lib.script_exceptions import DownloadError, CreateDirectoryError, HTTP404Error, HTTP503Error, NoFanartError, HTTPTimeout, ItemNotFoundError, CopyError
from resources.lib import language
from resources.lib.fileops import fileops
from xml.parsers.expat import ExpatError
from resources.lib.apply_filters import apply_filters
from resources.lib.settings import _settings
from resources.lib.media_setup import _media_listing as media_listing
### get addon info
__addon__       = xbmcaddon.Addon()
__addonid__     = __addon__.getAddonInfo('id')
__addonname__   = __addon__.getAddonInfo('name')
__author__      = __addon__.getAddonInfo('author')
__version__     = __addon__.getAddonInfo('version')
__localize__    = __addon__.getLocalizedString
__addonpath__   = __addon__.getAddonInfo('path')
__language__    = language.get_abbrev()

ACTION_PREVIOUS_MENU = ( 9, 10, 92, 216, 247, 257, 275, 61467, 61448, )



### clean up temporary folder
def cleanup(self):
    if self.fileops._exists(self.fileops.tempdir):
        dialog('update', percentage = 100, line1 = __localize__(32005), background = self.settings.background)
        log('Cleaning up temp files')
        for x in os.listdir(self.fileops.tempdir):
            tempfile = os.path.join(self.fileops.tempdir, x)
            self.fileops._delete(tempfile)
            if self.fileops._exists(tempfile):
                log('Error deleting temp file: %s' % tempfile, xbmc.LOGERROR)
        self.fileops._rmdir(self.fileops.tempdir)
        if self.fileops._exists(self.fileops.tempdir):
            log('Error deleting temp directory: %s' % self.fileops.tempdir, xbmc.LOGERROR)
        else:
            log('Deleted temp directory: %s' % self.fileops.tempdir, xbmc.LOGNOTICE)
    ### log results and notify user
    summary_tmp = __localize__(32012) + ': %s ' % self.fileops.downloadcount
    summary = summary_tmp + __localize__(32016)
    dialog('close', background = self.settings.background)
    # Some dialog checks
    if self.settings.notify:
        log('Notify on finished/error enabled')
        self.settings.background = False
    if xbmc.Player().isPlayingVideo() or self.silent:
        log('Silent finish because of playing a video or silent mode')
        self.settings.background = True
    if not self.settings.failcount < self.settings.failthreshold:
        log('Network error detected, script aborted', xbmc.LOGERROR)
        dialog('okdialog', line1 = __localize__(32010), line2 = __localize__(32011), background = self.settings.background)
    if self.mode == 'gui':
        log('GUI mode finished')
        if self._download_art_succes:
            xbmc.executebuiltin( 'XBMC.ReloadSkin()' )
    if not xbmc.abortRequested:
        dialog('okdialog', line1 = summary, background = self.settings.background)
    else:
        dialog('okdialog', line1 = __localize__(32010), line2 = summary, background = self.settings.background)


class Main:
    def __init__(self):
        initial_vars(self) 
        self.settings._get()        # Get settings from settings.xml
        self.settings._get_limit() # Get settings from settings.xml
        self.settings._check()      # Check if there are some faulty combinations present
        self.settings._initiallog() # Create debug log for settings
        self.settings._vars()       # Get some settings vars
        self.settings._artype_list()# Fill out the GUI and Arttype lists with enabled options
        runmode_args(self)          # Check for script call methods
        if initialise(self):
            # Check for silent background mode
            if self.silent:
                log('Silent mode')
                self.settings.background = True
                self.settings.notify = False
            # Check for gui mode
            elif self.mode == 'gui':
                log('set dialog true')
                self.settings.background = False
                self.settings.notify = False
            dialog('create', line1 = __localize__(32008), background = self.settings.background)
            # Check if mediatype is specified
            if not self.mediatype == '':
                # Check if medianame is specified
                if not self.medianame == '':
                    if self.mode == 'gui':
                        # GUI mode check is at the end of: 'def download_artwork'
                        solo_mode(self, self.mediatype, self.medianame)
                    else:
                        solo_mode(self, self.mediatype, self.medianame)
                # No medianame specified
                else:
                    if self.mediatype == 'movie':
                        self.Medialist = media_listing('movie')
                        log("Bulk mode: movie")
                        self.settings.movie_enable = 'true'
                        self.settings.tvshow_enable = 'false'
                        download_artwork(self, self.Medialist, self.movie_providers)
                    elif self.mediatype == 'tvshow':
                        self.settings.movie_enable = 'false'
                        self.settings.tvshow_enable = 'true'
                        self.Medialist = media_listing('tvshow')
                        log("Bulk mode: TV Shows")
                        download_artwork(self, self.Medialist, self.tv_providers)
                    elif self.mediatype == 'music':
                        log('Bulk mode: Music not yet implemented', xbmc.LOGNOTICE)
            # No mediatype is specified
            else:
                # activate both movie/tvshow for custom run
                if self.mode == 'custom':
                    self.settings.movie_enable = True
                    self.settings.tvshow_enable = True
                # Normal oprations check
                if self.settings.movie_enable:
                    self.Medialist = media_listing('movie')
                    self.mediatype = 'movie'
                    download_artwork(self, self.Medialist, self.movie_providers)
                else:
                    log('Movie fanart disabled, skipping', xbmc.LOGINFO)
                if self.settings.tvshow_enable:
                    self.Medialist = media_listing('tvshow')
                    self.mediatype = 'tvshow'
                    download_artwork(self, self.Medialist, self.tv_providers)
                else:
                    log('TV fanart disabled, skipping', xbmc.LOGINFO)
            _batch_download(self, self.download_list)
        else:
            log('Initialisation error, script aborting', xbmc.LOGERROR)
        # Make sure that files_overwrite option get's reset after downloading
        __addon__.setSetting(id="files_overwrite", value='false')
        # Cleaning up
        cleanup(self)
        finished_log(self)


### Declare standard vars   
def initial_vars(self):
    providers = provider.get_providers()
    self.settings = _settings()
    self.filters = apply_filters()
    self.movie_providers = providers['movie_providers']
    self.tv_providers = providers['tv_providers']
    self.music_providers = providers['music_providers']
    self.mediatype = ''
    self.medianame = ''
    self.mode = ''
    self.silent = ''
    self.gui_selected_type = ''
    self.gui_imagelist = ''
    self.download_list = []
    self._download_art_succes = False

### Report the total numbers of downloaded images (needs some work for correct totals)
def finished_log(self):
    log('## Download totaliser:')
    log('- Artwork: %s' % self.fileops.downloadcount, xbmc.LOGNOTICE)
    log('Movie download totals:')
    log('- Extrafanart: %s' % self.settings.count_movie_extrafanart, xbmc.LOGNOTICE)
    log('- Extrathumbs: %s' % self.settings.count_movie_extrathumbs, xbmc.LOGNOTICE)
    log('TV Show download totals:')
    log('- Extrafanart: %s' % self.settings.count_tvshow_extrafanart, xbmc.LOGNOTICE)

    
### Check for script starting arguments used by skins
def runmode_args(self):
    log("## Checking for starting arguments used by skins")
    try: log( "## arg 0: %s" % sys.argv[0] )
    except:   log( "## no arg0" )
    try: log( "## arg 1: %s" % sys.argv[1] )
    except:   log( "## no arg1" )
    try: log( "## arg 2: %s" % sys.argv[2] )
    except:   log( "## no arg2" )
    try: log( "## arg 3: %s" % sys.argv[3] )
    except:   log( "## no arg3" )
    try: log( "## arg 4: %s" % sys.argv[4] )
    except:   log( "## no arg4" )
    try: log( "## arg 5: %s" % sys.argv[5] )
    except:   log( "## no arg5" )
    try: log( "## arg 6: %s" % sys.argv[6] )
    except:   log( "## no arg6" )
    try: log( "## arg 7: %s" % sys.argv[7] )
    except:   log( "## no arg7" )
    try: log( "## arg 8: %s" % sys.argv[8] )
    except:   log( "## no arg8" )
    try: log( "## arg 9: %s" % sys.argv[9] )
    except:   log( "## no arg8" )
    try: log( "## arg 10: %s" % sys.argv[10] )
    except:   log( "## no arg8" )

### solo mode
def solo_mode(self, itemtype, itemname):
    # activate both movie/tvshow for custom r
    if self.mode == 'custom':
        self.settings.movie_enable = True
        self.settings.tvshow_enable = True
    if itemtype == 'movie':
        log("## Solo mode: Movie...")
        self.Medialist = media_listing('movie')
    elif itemtype == 'tvshow':
        self.Medialist = media_listing('tvshow')
        log("## Solo mode: TV Show...")
    else:
        log("Error: type must be one of 'movie', 'tvshow', aborting", xbmc.LOGERROR)
        return False
    log('Retrieving fanart for: %s' % itemname)
    for currentitem in self.Medialist:
        if itemname == currentitem["name"]:
            if itemtype == 'movie':
                self.Medialist = []
                self.Medialist.append(currentitem)
                download_artwork(self, self.Medialist, self.movie_providers)
            if itemtype == 'tvshow':
                self.Medialist = []
                self.Medialist.append(currentitem)
                download_artwork(self, self.Medialist, self.tv_providers)
            break

           
### load settings and initialise needed directories
def initialise(self):
    log("## Checking for downloading mode...")
    for item in sys.argv:
        # Check for download mode
        match = re.search("silent=(.*)" , item)
        if match:
            self.silent = match.group(1)
        # Check for download mode
        match = re.search("mode=(.*)" , item)
        if match:
            self.mode = match.group(1)
        # Check for mediatype mode
        match = re.search("mediatype=(.*)" , item)
        if match:
            self.mediatype = match.group(1)
            if self.mediatype == 'tvshow' or self.mediatype == 'movie' or self.mediatype == 'music':
                pass
            else:
                log('Error: invalid mediatype, must be one of movie, tvshow or music', xbmc.LOGERROR)
                return False
        # Check for medianame
        match = re.search("medianame=" , item)
        if match:
            self.medianame = item.replace("medianame=" , "")
        else:
            pass
    try:
        # Creates temp folder
        self.fileops = fileops()
    except CreateDirectoryError, e:
        log("Could not create directory: %s" % str(e))
        return False
    else:
        return True 


### download media fanart
def download_artwork(self, media_list, providers):
    self.processeditems = 0
    for currentmedia in media_list:
        ### check if XBMC is shutting down
        if xbmc.abortRequested:
            log('XBMC abort requested, aborting')
            break
        ### check if script has been cancelled by user
        if dialog('iscanceled', background = self.settings.background):
            break
        if not self.settings.failcount < self.settings.failthreshold:
            break
        # Check for stacked movies
        try:
            self.media_path = os.path.split(currentmedia["path"])[0].rsplit(' , ', 1)[1]
        except:
            self.media_path = os.path.split(currentmedia["path"])[0]
        # Fixes problems with rared movies
        if self.media_path.startswith("rar"):
            self.media_path = os.path.split(urllib.url2pathname(self.media_path.replace("rar://","")))[0]
        # Declare some vars
        self.media_id = currentmedia["id"]
        self.media_name = currentmedia["name"]
        dialog('update', percentage = int(float(self.processeditems) / float(len(media_list)) * 100.0), line1 = self.media_name, line2 = __localize__(32008), line3 = '', background = self.settings.background)
        log('########################################################')
        log('Processing media: %s' % self.media_name, xbmc.LOGNOTICE)
        log('ID: %s' % self.media_id)
        log('Path: %s' % self.media_path)
        # Declare the target folders
        self.target_extrafanartdirs = []
        self.target_extrathumbsdirs = []
        self.target_artworkdir = []
        artwork_dir = os.path.join(self.media_path + '/')
        extrafanart_dir = os.path.join(artwork_dir + 'extrafanart' + '/')
        extrathumbs_dir = os.path.join(artwork_dir + 'extrathumbs' + '/')
        self.target_artworkdir.append(artwork_dir)
        self.target_extrafanartdirs.append(extrafanart_dir)
        self.target_extrathumbsdirs.append(extrathumbs_dir)
        # Check if using the centralize option
        if self.settings.centralize_enable:
            if self.mediatype == 'tvshow':
                self.target_extrafanartdirs.append(self.settings.centralfolder_tvshows)
            elif self.mediatype == 'movie':
                self.target_extrafanartdirs.append(self.settings.centralfolder_movies)
        # Check for id used by source sites
        if self.mode == 'gui' and ((self.media_id == '') or (self.mediatype == 'tvshow' and self.media_id.startswith('tt'))):
            dialog('close', background = self.settings.background)
            dialog('okdialog','' ,self.media_name , __localize__(32030))
        elif self.media_id == '':
            log('%s: No ID found, skipping' % self.media_name, xbmc.LOGNOTICE)
        elif self.mediatype == 'tvshow' and self.media_id.startswith('tt'):
            log('%s: IMDB ID found for TV show, skipping' % self.media_name, xbmc.LOGNOTICE)
        # If correct ID found continue
        else:
            self.temp_image_list = []
            self.image_list = []
            # Run through all providers getting their imagelisting
            for self.provider in providers:
                if not self.settings.failcount < self.settings.failthreshold:
                    break
                artwork_result = ''
                xmlfailcount = 0
                while not artwork_result == 'pass' and not artwork_result == 'skipping':
                    if artwork_result == 'retrying':
                        time.sleep(self.settings.api_timedelay)
                    try:
                        self.temp_image_list = self.provider.get_image_list(self.media_id)
                    except HTTP404Error, e:
                        errmsg = '404: File not found'
                        artwork_result = 'skipping'
                    except HTTP503Error, e:
                        xmlfailcount = xmlfailcount + 1
                        errmsg = '503: API Limit Exceeded'
                        artwork_result = 'retrying'
                    except NoFanartError, e:
                        errmsg = 'No fanart found'
                        artwork_result = 'skipping'
                    except ItemNotFoundError, e:
                        errmsg = '%s not found' % self.media_id
                        artwork_result = 'skipping'
                    except ExpatError, e:
                        xmlfailcount = xmlfailcount + 1
                        errmsg = 'Error parsing xml: %s' % str(e)
                        artwork_result = 'retrying'
                    except HTTPTimeout, e:
                        self.settings.failcount = self.settings.failcount + 1
                        errmsg = 'Timed out'
                        artwork_result = 'skipping'
                    except DownloadError, e:
                        self.settings.failcount = self.settings.failcount + 1
                        errmsg = 'Possible network error: %s' % str(e)
                        artwork_result = 'skipping'
                    else:
                        artwork_result = 'pass'
                        for item in self.temp_image_list:
                            self.image_list.append(item)
                    if not xmlfailcount < self.settings.xmlfailthreshold:
                        artwork_result = 'skipping'
                    if not artwork_result == 'pass':
                        log('Error getting data from %s (%s): %s' % (self.provider.name, errmsg, artwork_result))
            if len(self.image_list) > 0:
                if (self.settings.limit_artwork and self.settings.limit_extrafanart_max < len(self.image_list)):
                    self.download_max = self.settings.limit_extrafanart_max
                else:
                    self.download_max = len(self.image_list)
                # Check for GUI mode
                if self.mode == 'gui':
                    log('here goes gui mode')
                    _gui_solomode(self)
                if self.mode == 'custom':
                    log('here goes custom mode')
                    _custom_process(self)
                else:
                    _download_process(self)
        log('Finished processing media: %s' % self.media_name, xbmc.LOGDEBUG)
        self.processeditems = self.processeditems + 1

### Processes the custom mode downloading of files
def _custom_process(self):
    if self.settings.movie_enable and self.mediatype == 'movie':
        for arttypes in self.settings.movie_arttype_list:
            for item in sys.argv:
                if item == arttypes['art_type']:
                    if arttypes['art_type'] == 'extrafanart':
                        _download_art(self, arttypes['art_type'], 'fanart', arttypes['filename'], self.target_extrafanartdirs,  arttypes['gui_string'])
                    elif arttypes['art_type'] == 'defaultthumb':
                        _download_art(self, arttypes['art_type'], 'poster', arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])    
                    elif arttypes['art_type'] == 'extrathumbs':
                        _download_art(self, arttypes['art_type'], 'thumb', arttypes['filename'], self.target_extrathumbsdirs,  arttypes['gui_string'])
                    else:
                        _download_art(self, arttypes['art_type'], arttypes['art_type'], arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])

    if self.settings.tvshow_enable and self.mediatype == 'tvshow':
        for arttypes in self.settings.tvshow_arttype_list:
            for item in sys.argv:
                if item == arttypes['art_type']:
                    if arttypes['art_type'] == 'extrafanart':
                        _download_art(self, arttypes['art_type'], 'fanart', arttypes['filename'], self.target_extrafanartdirs,  arttypes['gui_string'])
                    elif arttypes['art_type'] == 'defaultthumb':
                        _download_art(self, arttypes['art_type'],  str.lower(self.settings.tvshow_defaultthumb_type), arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])
                    else:
                        _download_art(self, arttypes['art_type'], arttypes['art_type'], arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])


### Processes the bulk/solo mode downloading of files
def _download_process(self):
    if self.settings.movie_enable and self.mediatype == 'movie':
        for arttypes in self.settings.movie_arttype_list:
            if arttypes['bulk_enabled']:
                if arttypes['art_type'] == 'extrafanart':
                    _download_art(self, arttypes['art_type'], 'fanart', arttypes['filename'], self.target_extrafanartdirs,  arttypes['gui_string'])
                elif arttypes['art_type'] == 'defaultthumb':
                    _download_art(self, arttypes['art_type'], 'poster', arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])    
                elif arttypes['art_type'] == 'extrathumbs':
                    _download_art(self, arttypes['art_type'], 'thumb', arttypes['filename'], self.target_extrathumbsdirs,  arttypes['gui_string'])
                else:
                    _download_art(self, arttypes['art_type'], arttypes['art_type'], arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])

    if self.settings.tvshow_enable and self.mediatype == 'tvshow':
        for arttypes in self.settings.tvshow_arttype_list:
            if arttypes['bulk_enabled']:
                if arttypes['art_type'] == 'extrafanart':
                    _download_art(self, arttypes['art_type'], 'fanart', arttypes['filename'], self.target_extrafanartdirs,  arttypes['gui_string'])
                elif arttypes['art_type'] == 'defaultthumb':
                    _download_art(self, arttypes['art_type'],  str.lower(self.settings.tvshow_defaultthumb_type), arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])
                else:
                    _download_art(self, arttypes['art_type'], arttypes['art_type'], arttypes['filename'], self.target_artworkdir,  arttypes['gui_string'])


### Retrieves imagelist for GUI solo mode
def _gui_solomode_imagelist(self, art_type, image_type):
    log('Retrieving image list for GUI')
    self.gui_imagelist = []
    # do some check for special cases
    if art_type == 'defaultthumb':
        image_type = str.lower(self.settings.tvshow_defaultthumb_type)
    elif art_type == 'extrafanart':
        image_type == 'fanart'
    elif art_type == 'extrathumbs':
        image_type == 'fanart'
    #retrieve list
    for artwork in self.image_list:
        if  artwork['type'] == image_type:
            self.gui_imagelist.append(artwork['url'])
            log('url: %s'%artwork['url'])
    log('Image list: %s' %self.gui_imagelist)
    if self.gui_imagelist == '':
        return False
    else:
        return True


### Artwork downloading
def _download_art_solo(self, art_type, image_type, filename, targetdirs, msg):
    log('Starting with processing: %s' %art_type)
    self._download_art_succes = False
    self.settings.failcount = 0
    # File naming
    if art_type == 'extrafanart':
        artworkfile = ('%s.jpg'%self.gui_imagelist['id'])
    elif art_type == 'extrathumbs':
        artworkfile = (filename+'%s.jpg' % str(downloaded_artwork+1))
    elif art_type == 'seasonthumbs' or art_type == 'seasonbanner':
        artworkfile = (filename+'%s.jpg' %artwork['season'])
    elif art_type == 'seasonposter':
        artworkfile = (filename+'%s.tbn' %artwork['season'])
    else: artworkfile = filename
    dialog('create', line1 = self.media_name, line2 = __localize__(32009) + ' ' + msg + ': ' + artworkfile)
    
    # Try downloading the file and catch errors while trying to
    try:
        self.fileops._downloadfile(self.image_url, artworkfile, targetdirs, 'true')
        self._download_art_succes = True
    except HTTP404Error, e:
        log("File does not exist at URL: %s" % str(e), xbmc.LOGWARNING)
        self._download_art_succes = False
    except HTTPTimeout, e:
        self.settings.failcount = self.settings.failcount + 1
        log("Error downloading file: %s, timed out" % str(e), xbmc.LOGERROR)
        self._download_art_succes = False
    except CreateDirectoryError, e:
        log("Could not create directory, skipping: %s" % str(e), xbmc.LOGWARNING)
        self._download_art_succes = False
    except CopyError, e:
        log("Could not copy file (Destination may be read only), skipping: %s" % str(e), xbmc.LOGWARNING)
        self._download_art_succes = False
    except DownloadError, e:
        self.settings.failcount = self.settings.failcount + 1
        log('Error downloading file: %s (Possible network error: %s), skipping' % (self.image_url, str(e)), xbmc.LOGERROR)
        self._download_art_succes = False
    dialog('close')
    dialog('okdialog', line1 = self.media_name, line2 = __localize__(32020) + ' ' + msg + ': ' + artworkfile)
    log('Finished with: %s' %art_type)


### Artwork downloading
def _download_art(self, art_type, image_type, filename, targetdirs, msg):
    log('Starting with processing: %s' %art_type)
    self.settings.failcount = 0
    current_artwork = 0
    downloaded_artwork = 0
    for artwork in self.image_list:
        imageurl = artwork['url']
        if image_type == artwork['type']:
            ### check if script has been cancelled by user
            if dialog('iscanceled', background = self.settings.background):
                dialog('close', background = self.settings.background)
                break
            if not self.settings.failcount < self.settings.failthreshold:
                break
            # File naming
            if art_type == 'extrafanart':
                artworkfile = ('%s.jpg'%artwork['id'])
            elif art_type == 'extrathumbs':
                artworkfile = (filename+'%s.jpg' % str(downloaded_artwork+1))
            elif art_type == 'seasonthumbs' or art_type == 'seasonbanner':
                artworkfile = (filename+'%s.jpg' %artwork['season'])
            elif art_type == 'seasonposter':
                artworkfile = (filename+'%s.jpg' %artwork['season'])
            else: artworkfile = filename
            #increase  artwork counter
            current_artwork = current_artwork + 1
            # Check for set limits
            limited = self.filters.do_filter(art_type, self.mediatype, artwork, downloaded_artwork)
            if limited[0] and art_type =='extrafanart':
                self.fileops._delete_file_in_dirs(artworkfile, targetdirs, limited[1])
            elif limited[0]:
                log('Skipped. Reason: %s' %limited[1])
            else:
                image = {}
                image['url'] = imageurl
                image['filename'] = artworkfile
                image['targetdirs'] = targetdirs
                item['media_name'] = self.media_name
                self.download_list.append(item)
    if current_artwork == 0:
        log('No %s found' %art_type)
    log('Finished with: %s' %art_type)

def _batch_download(self, image_list):
    downloaded_artwork = 0
    for image in image_list:
        url = image['url']
        filename = image['filename']
        targetdirs = image['targetdirs']
        media_name = image['media_name']
        # Try downloading the file and catch errors while trying to
        try:
            self.fileops._downloadfile(url, filename, targetdirs, self.settings.files_overwrite)
        except HTTP404Error, e:
            log("URL not found: %s" % str(e), xbmc.LOGERROR)
        except HTTPTimeout, e:
            self.settings.failcount = self.settings.failcount + 1
            log("Download timed out: %s" % str(e), xbmc.LOGERROR)
        except CreateDirectoryError, e:
            log("Could not create directory, skipping: %s" % str(e), xbmc.LOGWARNING)
            break
        except CopyError, e:
            log("Could not copy file (Destination may be read only), skipping: %s" % str(e), xbmc.LOGWARNING)
            break
        except DownloadError, e:
            self.settings.failcount = self.settings.failcount + 1
            log('Error downloading file: %s (Possible network error: %s), skipping' % (url, str(e)), xbmc.LOGERROR)
        else:
            downloaded_artwork = downloaded_artwork + 1
        dialog('update', percentage = int(float(downloaded_artwork) / float(len(image_list) * 100.0), line1 = media_name, line2 = __localize__(32009) + ' ' + msg, line3 = filename, background = self.settings.background))


def _gui_solomode(self):
    # Close the 'checking for artwork' dialog before opening the GUI list
    dialog('close', background = self.settings.background)
    self.GUI_type_list = []
    
    # Fill GUI art type list
    if self.mediatype == 'tvshow':
        for arttypes in self.settings.tvshow_arttype_list:
            if arttypes['solo_enabled'] == 'true':
                gui = arttypes['gui_string']
                self.GUI_type_list.append (gui)
    
    # Fill GUI art type list
    if self.mediatype == 'movie':
        for arttypes in self.settings.movie_arttype_list:
            if arttypes['solo_enabled'] == 'true':
                gui = arttypes['gui_string']
                self.GUI_type_list.append (gui)
    
    # 
    if len(self.GUI_type_list) == 1:
        self.GUI_type_list[0] = "True"
    if ( len(self.GUI_type_list) == 1 ) or _choice_type(self):
        self.tmp_image_list = False
        
        _gui_solomode_imagelist(self, self.gui_selected_type, self.gui_selected_type)
        log('Image put to GUI: %s' %self.gui_imagelist)
    
    # Download the selected image
    if self.gui_imagelist:
        if _choose_image(self):
            _download_art_solo(self, self.gui_selected_type, self.gui_selected_type, self.gui_selected_filename, self.target_artworkdir, self.gui_selected_msg)
            if not self._download_art_succes:
                xbmcgui.Dialog().ok(__localize__(32006) , __localize__(32007) )
    if not self.gui_imagelist and not self.gui_selected_type == '':
        log('no artwork')
        xbmcgui.Dialog().ok(self.media_name , self.gui_selected_msg + ' ' + __localize__(32022) )
    elif self._download_art_succes:
        log('Download succesfull')
    else:
        log('cancelled')
        xbmcgui.Dialog().ok(__localize__(32017) , __localize__(32018) )

# This creates the art type selection dialog. The string id is the selection constraint for what type has been chosen.
def _choice_type(self):
    select = xbmcgui.Dialog().select(__addonname__ + ': ' + __localize__(32015) , self.GUI_type_list)
    self.gui_selected_type = ''
    if select == -1: 
        log( "### Canceled by user" )
        return False
    else:
        # Check what artwork type has been chosen and parse the image restraints
        if self.mediatype == 'tvshow':
            for arttypes in self.settings.tvshow_arttype_list:
                if self.GUI_type_list[select] == arttypes['gui_string']:
                    self.gui_selected_type = arttypes['art_type']
                    self.gui_selected_filename = arttypes['filename']
                    self.gui_selected_msg = arttypes['gui_string']
                    return True
        if self.mediatype == 'movie':
            for arttypes in self.settings.movie_arttype_list:
                if self.GUI_type_list[select] == arttypes['gui_string']:
                    self.gui_selected_type = arttypes['art_type']
                    self.gui_selected_filename = arttypes['filename']
                    self.gui_selected_msg = arttypes['gui_string']
                    return True
        else:
            return False

def _choose_image(self):
    log( "### image list: %s" % self.gui_imagelist)
    self.image_url = MyDialog(self.gui_imagelist)
    if self.image_url:
        return True
    else:
        return False


class MainGui( xbmcgui.WindowXMLDialog ):
    def __init__( self, *args, **kwargs ):
        xbmcgui.WindowXMLDialog.__init__( self )
        xbmc.executebuiltin( "Skin.Reset(AnimeWindowXMLDialogClose)" )
        xbmc.executebuiltin( "Skin.SetBool(AnimeWindowXMLDialogClose)" )
        self.listing = kwargs.get( "listing" )

    def onInit(self):
        try :
            self.img_list = self.getControl(6)
            self.img_list.controlLeft(self.img_list)
            self.img_list.controlRight(self.img_list)
            self.getControl(3).setVisible(False)
        except :
            print_exc()
            self.img_list = self.getControl(3)

        self.getControl(5).setVisible(False)
        self.getControl(1).setLabel(__localize__(32019))

        for image in self.listing :
            listitem = xbmcgui.ListItem( image.split("/")[-1] )
            listitem.setIconImage( image )
            listitem.setLabel2(image)
            log( "### image: %s" % image )
            self.img_list.addItem( listitem )
        self.setFocus(self.img_list)

    def onAction(self, action):
        if action in ACTION_PREVIOUS_MENU:
            self.close()


    def onClick(self, controlID):
        log( "### control: %s" % controlID )
        if controlID == 6 or controlID == 3: 
            num = self.img_list.getSelectedPosition()
            log( "### position: %s" % num )
            self.selected_url = self.img_list.getSelectedItem().getLabel2()
            self.close()

    def onFocus(self, controlID):
        pass

def MyDialog(tv_list):
    w = MainGui( "DialogSelect.xml", __addonpath__, listing=tv_list )
    w.doModal()
    try: return w.selected_url
    except: 
        print_exc()
        return False
    del w


### Start of script
if (__name__ == "__main__"):
    log("######## Extrafanart Downloader: Initializing...............................")
    log('## Add-on ID   = %s' % str(__addonid__))
    log('## Add-on Name = %s' % str(__addonname__))
    log('## Authors     = %s' % str(__author__))
    log('## Version     = %s' % str(__version__))
    Main()
    log('script stopped')
