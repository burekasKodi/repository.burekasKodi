# -*- coding: utf-8 -*-

import os
import shutil
import sys
import urllib.request, urllib.parse, urllib.error
from urllib.request import urlopen
from urllib.parse import quote
import xbmc
import xbmcaddon
import xbmcgui,xbmcplugin
import xbmcvfs
import uuid

from unicodedata import normalize
from os import path
import codecs
from requests import get
from json import loads, load
from time import time

import json
import re

__addon__ = xbmcaddon.Addon()
__author__     = __addon__.getAddonInfo('author')
__scriptid__   = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__    = __addon__.getAddonInfo('version')
__language__   = __addon__.getLocalizedString

__cwd__        = xbmcvfs.translatePath( __addon__.getAddonInfo('path') )
__profile__    = xbmcvfs.translatePath( __addon__.getAddonInfo('profile') )
__resource__   = xbmcvfs.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) )
__temp__       = xbmcvfs.translatePath( os.path.join( __profile__, 'temp', '') )

if xbmcvfs.exists(__temp__):
  shutil.rmtree(__temp__)
xbmcvfs.mkdirs(__temp__)

sys.path.append (__resource__)

from OSUtilities import OSDBServer, log, hashFile, normalizeString, searchForIMDBID, checkAndParseIfTitleIsTVshowEpisode, caching_json, get_now_played, get_more_data, is_local_file_tvshow

def Search( item ):
  search_data = []
  try:
    search_data = OSDBServer().searchsubtitles(item)
  except:
    log( __name__, "failed to connect to service for subtitle search")
    xbmc.executebuiltin(('Notification(%s,%s)' % (__scriptname__ , __language__(32001))))
    return

  if search_data != None:
    #optional but recommanded
    if isinstance(search_data, dict):  
        log( __name__, "received data has a new format, convert it to list")  
        search_data = [v for v in list(search_data.values())]

    search_data.sort(key=lambda x: [not x['MatchedBy'] == 'moviehash',
				     not os.path.splitext(x['SubFileName'])[0] == os.path.splitext(os.path.basename(urllib.parse.unquote(item['file_original_path'])))[0],
				     not normalizeString(xbmc.getInfoLabel("VideoPlayer.OriginalTitle")).lower() in x['SubFileName'].replace('.',' ').lower(),
				     not x['LanguageName'] == PreferredSub])
    log( __name__, "search_data sorted: %s" %repr(search_data))
	
    for item_data in search_data:
      ## hack to work around issue where Brazilian is not found as language in XBMC
      if item_data["LanguageName"] == "Brazilian":
        item_data["LanguageName"] = "Portuguese (Brazil)"

      if ((item['season'] == item_data['SeriesSeason'] and
          item['episode'] == item_data['SeriesEpisode']) or
          (item['season'] == 0 and item['episode'] == 0) or
          (item['season'] == '' and item['episode'] == '') ## for file search, season and episode == ""
         ):
        listitem = xbmcgui.ListItem(label          = item_data["LanguageName"],
                                    label2         = item_data["SubFileName"],
                                    )
        listitem.setArt({'icon': str(int(round(float(item_data["SubRating"])/2))), 
                         'thumb': item_data["ISO639"]}
                        )

        listitem.setProperty( "sync", ("false", "true")[str(item_data["MatchedBy"]) == "moviehash"] )
        listitem.setProperty( "hearing_imp", ("false", "true")[int(item_data["SubHearingImpaired"]) != 0] )
        url = "plugin://%s/?action=download&link=%s&ID=%s&filename=%s&format=%s" % (__scriptid__,
                                                                          item_data["ZipDownloadLink"],
                                                                          item_data["IDSubtitleFile"],
                                                                          item_data["SubFileName"],
                                                                          item_data["SubFormat"]
                                                                          )

        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=url,listitem=listitem,isFolder=False)


def Download(id,url,format,stack=False):
  subtitle_list = []
  exts = [".srt", ".sub", ".txt", ".smi", ".ssa", ".ass" ]
  if stack:         ## we only want XMLRPC download if movie is not in stack,
                    ## you can only retreive multiple subs in zip
    result = False
  else:
    subtitle = os.path.join(__temp__, "%s.%s" %(str(uuid.uuid4()), format))
    try:
      result = OSDBServer().download(id, subtitle)
    except:
      log( __name__, "failed to connect to service for subtitle download")
      return subtitle_list
  if not result:
    log( __name__,"Download Using HTTP")
    zip = os.path.join( __temp__, "OpenSubtitles.zip")
    f = urllib.request.urlopen(url)
    with open(zip, "wb") as subFile:
      subFile.write(f.read())
    subFile.close()
    xbmc.sleep(500)
    xbmc.executebuiltin(('Extract("%s","%s")' % (zip,__temp__,)), True)
    for file in xbmcvfs.listdir(zip)[1]:
      file = os.path.join(__temp__, file)
      if (os.path.splitext( file )[1] in exts):
        subtitle_list.append(file)
  else:
    subtitle_list.append(subtitle)

  if xbmcvfs.exists(subtitle_list[0]):
    return subtitle_list


#========================================================
# Not in use: Very old method of wizdom with TVDB
#========================================================

#def getTVshowOriginalTitleByIMDBidandTVDBapi():   
#    labelTVShowTitle = xbmc.getInfoLabel("ListItem.TVShowTitle")
#    #labelIMDBID = xbmc.getInfoLabel("ListItem.IMDBNumber")  #quasar return show imdb id , Library return tvdb episode id 
#    #Library returns tvdb show ID because json imdbnumner rerurn tvdb, quasar tvdb id return empty because there is no DBID   
#    imdb_num = getIMDBnumberByTVShowTitle_WithWizdom(labelTVShowTitle) #by wizdom   

#    link = "http://thetvdb.com/api/GetSeriesByRemoteID.php?imdbid=%s" %imdb_num
#    f = urllib.urlopen(link)
#    myfile = f.read()
       
#    matchShow = re.search(r'(?<=<SeriesName>)(.*)(?=</SeriesName>)' , myfile)
#    originalShowTitle = matchShow.group(1)
    
#    return originalShowTitle


#def get_wizdom_domain():
#    try:
#        domain = str(get('https://pastebin.com/raw/h5r8NmHd').text)
#        if len(domain) > 8:
#            raise Exception
#        return domain
#    except Exception as err:
#        #wlog('Caught Exception: error in finding domain: %s' % format(err))
#        return 'xyz'

#def getIMDBnumberByTVShowTitle_WithWizdom(title):
#    domain = get_wizdom_domain()   
#    imdb_id = urlopen("http://api.wizdom."+domain+"/search.tv.php?name="+quote(title)).read()
#    return imdb_id

#=============================================================
# Not in use: New idea of wizdom (Get original name of tv show by using TMDB for getting imdb & then using tvdb, long way)
#=============================================================

#def getTVshowOriginalTitleByIMDBidandTMDBapi():   
#    labelTVShowTitle = xbmc.getInfoLabel("ListItem.TVShowTitle")
#    labelYear = xbmc.getInfoLabel("ListItem.Year")
#    #labelIMDBID = xbmc.getInfoLabel("ListItem.IMDBNumber")  #quasar return show imdb id , Library return tvdb episode id 
#    #Library returns tvdb show ID because json imdbnumner rerurn tvdb, quasar tvdb id return empty because there is no DBID   
#    imdb_num = getIMDBnumberByTVShowTitle_WithTMDB(labelTVShowTitle, labelYear) #by wizdom   

#    link = "http://thetvdb.com/api/GetSeriesByRemoteID.php?imdbid=%s" %imdb_num
#    f = urllib.urlopen(link)
#    myfile = f.read()
       
#    matchShow = re.search(r'(?<=<SeriesName>)(.*)(?=</SeriesName>)' , myfile)
#    originalShowTitle = matchShow.group(1)
    
#    return originalShowTitle

#def getIMDBnumberByTVShowTitle_WithTMDB(title, year):
#    tmdbKey = '653bb8af90162bd98fc7ee32bcbbfb3d'
#    filename = 'wizdom.search.tmdb.%s.%s.%s.json' % ("tv",lowercase_with_underscores(title), year)
#    if year > 0:
#        url = "http://api.tmdb.org/3/search/%s?api_key=%s&query=%s&year=%s&language=en" % (
#			"tv",tmdbKey, title, year)
#    else:
#        url = "http://api.tmdb.org/3/search/%s?api_key=%s&query=%s&language=en" % (
#			"tv",tmdbKey, title)
    
#    log( __name__, "searchTMDB: %s" % url)
#    json = caching_json(filename,url)
#    #log( __name__, 'BBB: JSON : %s' % json)

#    try:
#        tmdb_id = int(json["results"][0]["id"])
#    except Exception as err:
#        log( __name__, 'Caught Exception: error searchTMDB: %s' % format(err))
#        return 0
    
#    filename = 'wizdom.tmdb.%s.json' % (tmdb_id)
#    url = "http://api.tmdb.org/3/%s/%s/external_ids?api_key=%s&language=en" % ("tv",tmdb_id, tmdbKey)
#    response = get(url)
#    json = loads(response.text)
#    try:
#        imdb_id = json["imdb_id"]
#    except Exception:
#        log( __name__, 'Caught Exception: error searching movie: %s' % format(err))
#        return 0

#    #log( __name__, 'BBB: IMDB : %s' % imdb_id)
#    return imdb_id

#==========================================================================================================
# Trying to get original name of tv show from kodi database By Episode details (According to tvdb scraper)
#==========================================================================================================

def getTVshowOriginalTitleByJSONandDBid(source="notPlaying"): ###### burekas
    try:
        if (source=="notPlaying"):
            labelDBID = xbmc.getInfoLabel("ListItem.DBID")
        else:
            labelDBID = xbmc.getInfoLabel("VideoPlayer.DBID")        
        
        originalShowTitle = ''
        
        requestEpisodeDetails = {"jsonrpc": "2.0", "id": 1 , "method": "VideoLibrary.GetEpisodeDetails", "params": {"episodeid": int(labelDBID), "properties": ["tvshowid"]}}
        resultsEpisodeDetails = json.loads(xbmc.executeJSONRPC(json.dumps(requestEpisodeDetails)))
        
        tvshowDBID = resultsEpisodeDetails["result"]["episodedetails"]["tvshowid"]
        
        requestTVShowDetails = {"jsonrpc": "2.0", "id": 1 , "method": "VideoLibrary.GetTVShowDetails", "params": {"tvshowid": int(tvshowDBID), "properties": ["originaltitle"]}}
        resultsTVShowDetails = json.loads(xbmc.executeJSONRPC(json.dumps(requestTVShowDetails)))
        
        #log( __name__, "AAAA Details Episode '%s'" % resultsEpisodeDetails)
        #log( __name__, "AAAA Details Show '%s'" % requestTVShowDetails)
        
        tvshowOriginalTitle = resultsTVShowDetails["result"]["tvshowdetails"]["originaltitle"]
        
        originalShowTitle = tvshowOriginalTitle

        '''
        request2 = {"jsonrpc": "2.0", "id": 1 , "method": "VideoLibrary.GetTVShowDetails", "params": {"tvshowid": int(tvshowid), "properties": ["file"]}}
        resultsAll2 = json.loads(xbmc.executeJSONRPC(json.dumps(request2)))
        tvshowFile = resultsAll2["result"]["tvshowdetails"]["file"]
        matchShow = re.search(r'(?i)Shows\/(.*?)\ \(' , tvshowFile)
        originalShowTitle = matchShow.group(1)
        '''

        return originalShowTitle

    except Exception as err:
        log('Caught Exception: error getTVshowOriginalTitleByJSONandDBid: %s' % format(err))
        originalShowTitle = ''			
        return originalShowTitle 


#=============================================================
# New idea of wizdom (Get original name of tv show by using TMDB for getting the original name)
#=============================================================

def getTVshowOriginalTitleByTMDBapi(source="notPlaying"): ###### burekas
    try:
        if (source=="notPlaying"):
            labelTVShowTitle = xbmc.getInfoLabel("ListItem.TVShowTitle")
            labelYear = xbmc.getInfoLabel("ListItem.Year")
        else:
            labelTVShowTitle = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
            labelYear = xbmc.getInfoLabel("VideoPlayer.Year")
            
        originalTitle = ''
        
        tmdbKey = '653bb8af90162bd98fc7ee32bcbbfb3d'
        filename = 'subs.search.tmdb.%s.%s.%s.json' % ("tv",lowercase_with_underscores(labelTVShowTitle), labelYear)
        
        if int(labelYear) > 0:
            #url = "http://api.tmdb.org/3/search/%s?api_key=%s&query=%s&year=%s&language=en" % ("tv",tmdbKey, labelTVShowTitle, labelYear)
            url = "http://api.themoviedb.org/3/search/%s?api_key=%s&query=%s&year=%s&language=en" % ("tv",tmdbKey, labelTVShowTitle, labelYear)
        else:
            #url = "http://api.tmdb.org/3/search/%s?api_key=%s&query=%s&language=en" % ("tv",tmdbKey, labelTVShowTitle)
            url = "http://api.themoviedb.org/3/search/%s?api_key=%s&query=%s&language=en" % ("tv",tmdbKey, labelTVShowTitle)
        
        log( __name__, "searchTMDB for original tv title: %s" % url)
        
        json_results = get_TMDB_data_popularity_and_votes_sorted(url,filename)
        '''
        json = caching_json(filename,url)

        resultsLen = len(json["results"])			
        itemIndex = -1
        voteCountMax = 0			
        popularityMax = 0						
        itemIndexMax = 0			
        for item in json['results']:
            itemIndex = itemIndex+1				
            if (item['vote_count'] > voteCountMax and item['popularity'] > popularityMax):
                voteCountMax = item['vote_count']
                popularityMax = item['popularity']						
                itemIndexMax = itemIndex
    
        if resultsLen > 0 :			
            #originalTitle = json["results"][itemIndexMax]["original_name"]
            originalTitle = json["results"][itemIndexMax]["name"]

        #log( __name__, 'originalTitle : %s' % originalTitle)
        '''
        
        try:    originalTitle = json_results[0]["name"]
        except:
            log( "[%s]" % (e,))
            return ''         
               
        return originalTitle
    
    except Exception as err:
        log( __name__, 'Caught Exception: error searchTMDB: %s' % format(err))
        originalTitle = ''		
        return originalTitle


def get_TMDB_data_popularity_and_votes_sorted(url,filename):    ##### burekas
    log("searchTMDB: %s" % url)
    json = caching_json(filename,url)
    json_results = json["results"]
    log("searchTMDB: json_results - " + repr(json_results))
    json_results.sort(key = lambda x:x["popularity"], reverse=True)
    json_results.sort(key = lambda x:x["vote_count"], reverse=True)
    log("searchTMDB: json_results sorted - " + repr(json_results))

    return json_results

def lowercase_with_underscores(_str):   ####### burekas
    return normalize('NFKD', _str).encode('utf-8','ignore').decode('utf-8')
    #return normalize('NFKD', _str)
    #return normalize('NFKD', _str).encode('utf-8', 'ignore')    
    #return normalize('NFKD', unicode(unicode(_str, 'utf-8'))).encode('utf-8', 'ignore')

def getOriginalTitle(): ###### burekas

    if xbmc.getInfoLabel("VideoPlayer.TVshowtitle").isascii():
        return normalizeString(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))  # Show

    #First, check if database has the original title.
    labelTVShowTitle = getTVshowOriginalTitleByJSONandDBid("playing")    ##using kodi database json
    #If not, try get the original title by using tmdb api
    if (labelTVShowTitle == "" or not labelTVShowTitle.isascii()):
        labelTVShowTitle = getTVshowOriginalTitleByTMDBapi("playing")  ##New way using tmdb api

    return labelTVShowTitle

def takeTitleFromFocusedItem():
    labelMovieTitle = xbmc.getInfoLabel("ListItem.OriginalTitle")
    labelYear = xbmc.getInfoLabel("ListItem.Year")
    labelTVShowTitle = xbmc.getInfoLabel("ListItem.TVShowTitle") #xbmc.getInfoLabel("ListItem.OriginalTitle")
    labelSeason = xbmc.getInfoLabel("ListItem.Season")
    labelEpisode = xbmc.getInfoLabel("ListItem.Episode")
    labelType = xbmc.getInfoLabel("ListItem.DBTYPE")  #movie/tvshow/season/episode	
    isItMovie = labelType == 'movie' or xbmc.getCondVisibility("Container.Content(movies)")
    isItEpisode = labelType == 'episode' or xbmc.getCondVisibility("Container.Content(episodes)")
    labelDBID = xbmc.getInfoLabel("ListItem.DBID")

    #log( __name__, "AAAA TVSHOWTITLE '%s'" % labelTVShowTitle)
    #log( __name__, "AAAA ORIGINALTITLE '%s'" % labelMovieTitle)
    #log( __name__, "AAAA Year '%s'" % labelYear)
    #log( __name__, "AAAA DBID '%s'" % labelDBID)
    #log( __name__, "AAAA IMDB '%s'" % xbmc.getInfoLabel("ListItem.IMDBNumber"))

    #If item is TVShow and in the library => When titles are not in english
    if isItEpisode and labelDBID != "":
        #First, check if database has the original title.
        labelTVShowTitle = getTVshowOriginalTitleByJSONandDBid('notPlaying')    ##using kodi database json
        #If not, try get the original title by using the imdb id (by wizdom) and parsing the title by tvdb api
        if (labelTVShowTitle == "" or not labelTVShowTitle.isascii()):
            labelTVShowTitle = getTVshowOriginalTitleByTMDBapi('notPlaying')  ##New way using tmdb api
            #labelTVShowTitle = getTVshowOriginalTitleByIMDBidandTMDBapi()  ## New way, Not in use           
            #labelTVShowTitle = getTVshowOriginalTitleByIMDBidandTVDBapi()  ## Old way
        
    title = 'SearchFor...'
    if isItMovie and labelMovieTitle and labelYear:
        title = ("%s %s" % (labelMovieTitle, labelYear))
    elif isItEpisode and labelTVShowTitle and labelSeason and labelEpisode:
        title = ("%s S%.2dE%.2d" % (labelTVShowTitle, int(labelSeason), int(labelEpisode)))

    return title

def get_params(string=""):
  param=[]
  if string == "":
    paramstring=sys.argv[2]
  else:
    paramstring=string
  if len(paramstring)>=2:
    params=paramstring
    cleanedparams=params.replace('?','')
    if (params[len(params)-1]=='/'):
      params=params[0:len(params)-2]
    pairsofparams=cleanedparams.split('&')
    param={}
    for i in range(len(pairsofparams)):
      splitparams={}
      splitparams=pairsofparams[i].split('=')
      if (len(splitparams))==2:
        param[splitparams[0]]=splitparams[1]

  return param

params = get_params()

if params['action'] == 'search' or params['action'] == 'manualsearch':
  log( __name__, "action '%s' called" % params['action'])
  item = {}

  if xbmc.Player().isPlaying():
    item['temp']               = False
    item['rar']                = False
    item['mansearch']          = False
    item['imdb_id']            = xbmc.Player().getVideoInfoTag().getIMDBNumber()
    item['dbtype']             = ''
    item['year']               = xbmc.getInfoLabel("VideoPlayer.Year")                          # Year
    item['season']             = str(xbmc.getInfoLabel("VideoPlayer.Season"))                   # Season
    item['episode']            = str(xbmc.getInfoLabel("VideoPlayer.Episode"))                  # Episode
    item['tvshow']             = getOriginalTitle()                                             # Show
    item['title']              = normalizeString(xbmc.getInfoLabel("VideoPlayer.OriginalTitle"))# try to get original title
    item['file_original_path'] = xbmc.Player().getPlayingFile()                                 # Full path of a playing file
    item['3let_language']      = [] #['scc','eng']
    
    if not item['tvshow'] and not (item['title'] and item['year']) :
        now_play_data = get_now_played()
        item['title'],item['year'],item['season'],item['episode']=get_more_data(now_play_data['label'])
        if (is_local_file_tvshow(item)):
            item["tvshow"] = item["title"]
        else:
            item['title'] = ("%s %s" % (item['title'], item['year']))

  else:
    item['temp']       = False
    item['rar']        = False
    item['mansearch']  = False
    item['imdb_id']    = xbmc.getInfoLabel("ListItem.IMDBNumber")    
    item['dbtype']     = xbmc.getInfoLabel("ListItem.DBTYPE")        
    item['year']       = xbmc.getInfoLabel("ListItem.Year")
    item['season']     = xbmc.getInfoLabel("ListItem.Season")
    item['episode']    = xbmc.getInfoLabel("ListItem.Episode")
    item['tvshow'] = ""
    item['title'] = takeTitleFromFocusedItem()
    item['file_original_path'] = ""
    item['3let_language'] = []

  PreferredSub = params.get('preferredlanguage')

  for lang in urllib.parse.unquote(params['languages']).split(","):
    if lang == "Portuguese (Brazil)":
      lan = "pob"
    elif lang == "Greek":
      lan = "ell"
    else:
      lan = xbmc.convertLanguage(lang,xbmc.ISO_639_2)

    item['3let_language'].append(lan)

  if item['title'] == "":
    log( __name__, "VideoPlayer.OriginalTitle not found")
    item['title']  = normalizeString(xbmc.getInfoLabel("VideoPlayer.Title"))      # no original title, get just Title

  if str(item['episode']).lower().find("s") > -1:                                      # Check if season is "Special"
    item['season'] = "0"                                                          #
    item['episode'] = item['episode'][-1:]

  if ( item['file_original_path'].find("http") > -1 ):
    item['temp'] = True

  elif ( item['file_original_path'].find("rar://") > -1 ):
    item['rar']  = True
    item['file_original_path'] = os.path.dirname(item['file_original_path'][6:])

  elif ( item['file_original_path'].find("stack://") > -1 ):
    stackPath = item['file_original_path'].split(" , ")
    item['file_original_path'] = stackPath[0][8:]

  if 'searchstring' in params:
    item['mansearch'] = True
    item['mansearchstr'] = urllib.parse.unquote(params['searchstring'])
    item['tvshow'], item['season'], item['episode'], item['dbtype'] = checkAndParseIfTitleIsTVshowEpisode(item['mansearchstr'])
    log( __name__, "Parsed item tvshow result: " + item['tvshow'])        

  if item['mansearch'] == True:
    if item['tvshow'] == 'NotTVShowEpisode':
      item['title'] = item['mansearchstr']
      _query = item['title'].rsplit(' ', 1)[0]    

      try:
        item['year'] = item['title'].rsplit(' ', 1)[1]

        if item['year'].isdigit():
          if int(item['year']) > 1900:
            item['imdb_id'] = searchForIMDBID(_query, item)
          else:
            #item['year'] is not present a year
            item['imdb_id'] = ''
        else:
          item['imdb_id'] = '' 
      except:  
        item['imdb_id'] = ''        
        
    else:  # TVShowEpisode
      _query = item['tvshow']    
    
      _season = item['season'].split("0")
      _episode = item['episode'].split("0")
      if _season[0] == '':
        item['season'] = _season[1]
      if _episode[0] == '':
        item['episode'] = _episode[1]
      
      item['imdb_id'] = searchForIMDBID(_query, item)

  elif 'tt' not in item['imdb_id'] and item['mansearch'] == False:
    _query = item['title'].rsplit(' ', 1)[0]
    if item['dbtype'] == 'episode':
      item['tvshow'] = _query
    
    if item['title'] != 'SearchFor...':
      item['imdb_id'] = searchForIMDBID(_query, item)

  else:
    item['imdb_id'] = ''    

  Search(item)

elif params['action'] == 'download':
  subs = Download(params["ID"], params["link"],params["format"])
  for sub in subs:
    listitem = xbmcgui.ListItem(label=sub)
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=sub,listitem=listitem,isFolder=False)


xbmcplugin.endOfDirectory(int(sys.argv[1]))
