# -*- coding: utf-8 -*- 

import os
import sys
import xbmc
import struct
import urllib.request, urllib.parse, urllib.error
import xbmcvfs
import xmlrpc.client
import xbmcaddon
import unicodedata
import PTN
import re

##### burekas fix
#from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode, quote, quote_plus

##### burekas fix
from os import path
from json import loads, load, dumps
from time import time

__addon__      = xbmcaddon.Addon()
__version__    = __addon__.getAddonInfo('version') # Module version
__scriptname__ = "XBMC Subtitles Unofficial"

__profile__ = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))
__temp__ = xbmcvfs.translatePath(os.path.join(__profile__, 'temp', ''))

BASE_URL_XMLRPC = "http://api.opensubtitles.org/xml-rpc"

class OSDBServer:
    def __init__( self, *args, **kwargs ):
        self.server = xmlrpc.client.Server( BASE_URL_XMLRPC, verbose=0 )
        login = self.server.LogIn(__addon__.getSetting( "OSuser" ), __addon__.getSetting( "OSpass" ), "en", "%s_v%s" %(__scriptname__.replace(" ","_"),__version__))
        self.osdb_token  = login[ "token" ]
    
    def searchsubtitles( self, item):
        if ( self.osdb_token ) :
            searchlist  = []
            ## Manual Search (Playing & Not Playing ##
            if item['mansearch']:
                OS_search_string = item['mansearchstr'].replace(" ","+");
                log( __name__ , "Manual Search String [ %s ]" % (OS_search_string,))
                if item['dbtype'] == 'episode':
                    searchlist = [{'season'        : item['season'],
                                   'sublanguageid' : ",".join(item['3let_language']),
                                   'imdbid'        : item['imdb_id'].replace('tt',''),
                                   'query'         : OS_search_string,
                                   'episode'       : item['episode']
                                  }]
                else:
                    searchlist = [{'sublanguageid': ",".join(item['3let_language']),
                                   'query'        : OS_search_string,
                                   'imdbid'       : item['imdb_id'].replace('tt','')
                                 }]
                log( __name__ , "SearchSubtitles searchlist String [ %s ]" % (searchlist,))                                
                search = self.server.SearchSubtitles( self.osdb_token, searchlist )
                try:
                    data = search["data"]
                    return data
                except:
                    return [] #None
            
            ## Not Playing ##
            if not xbmc.Player().isPlaying():          
                OS_search_string = item['title'].replace(" ","+");
                log( __name__ , "Offline Search String [ %s ]" % (OS_search_string,))
                if item['dbtype'] == 'episode':
                    searchlist.append({'season'        : item['season'],
                                       'sublanguageid' : ",".join(item['3let_language']),
                                       'imdbid'        : item['imdb_id'].replace('tt',''),
                                       'query'         : OS_search_string,
                                       'episode'       : item['episode']
                                      })
                else:
                    searchlist.append({'sublanguageid': ",".join(item['3let_language']),
                           'query'        : OS_search_string,
                           'imdbid'       : item['imdb_id'].replace('tt','')
                         })
                
            ## Playing ##       
            else:       
                ## TV Show ## 
                if len(item['tvshow']) > 0:
                    OS_search_string = ("%s S%.2dE%.2d" % (item['tvshow'],
                                                            int(item['season']),
                                                            int(item['episode']),)
                                                          ).replace(" ","+")           
                ## Movie ##
                else:
                    if str(item['year']) == "":
                        item['title'], item['year'] = xbmc.getCleanMovieTitle( item['title'] )
                    
                    OS_search_string = item['title'].replace(" ","+")           
                  
                log( __name__ , "Online Search String [ %s ]" % (OS_search_string,))          
                          
                #searchlist.append({'sublanguageid': ",".join(item['3let_language']),
                #               'query'        : OS_search_string,
                #               'imdbid'       : item['imdb_id'].replace('tt','')
                #             })
                
                if item["tvshow"] and (item['dbtype'] == 'episode' or (item['season'] and item['episode'])):
                    searchlist = [{'season'        : item['season'],
                                   'sublanguageid' : ",".join(item['3let_language']),
                                   'imdbid'        : item['imdb_id'].replace('tt',''),
                                   'query'         : OS_search_string,
                                   'episode'       : item['episode']
                                  }]
                else:
                    searchlist = [{'sublanguageid': ",".join(item['3let_language']),
                                   'query'        : OS_search_string,
                                   'imdbid'       : item['imdb_id'].replace('tt','')
                                 }]      
              
            if not item['temp']:
                try:
                    size, hash = hashFile(item['file_original_path'], item['rar'])
                    log( __name__ ,"OpenSubtitles module hash [%s] and size [%s]" % (hash, size,))
                    searchlist.append({'sublanguageid' :",".join(item['3let_language']),
                                        'moviehash'    :hash,
                                        'moviebytesize':str(size)
                                      })
                except:
                    pass   
            
            log( __name__ , "SearchSubtitles searchlist String [ %s ]" % (searchlist,))          
            search = self.server.SearchSubtitles( self.osdb_token, searchlist )
            
            log( __name__ ,"OpenSubtitles search result: %s" % repr(search))            
            try:
                data = search["data"]
                return data
            except:
                return [] #None      
    
    def download(self, ID, dest):
        try:
            import zlib, base64
            down_id=[ID,]
            result = self.server.DownloadSubtitles(self.osdb_token, down_id)
            if result["data"]:
                local_file = open(dest, "w" + "b")
                d = zlib.decompressobj(16+zlib.MAX_WBITS)
                data = d.decompress(base64.b64decode(result["data"][0]["data"]))
                local_file.write(data)
                local_file.close()
                log( __name__,"Download Using XMLRPC")
                return True
            return False
        except:
            return False

def log(module, msg):
    xbmc.log(("### [%s] - %s" % (module,msg,)),level=xbmc.LOGDEBUG ) 

def hashFile(file_path, rar):
    if rar:
      return OpensubtitlesHashRar(file_path)
      
    log( __name__,"Hash Standard file")  
    longlongformat = 'q'  # long long
    bytesize = struct.calcsize(longlongformat)
    f = xbmcvfs.File(file_path)
    
    filesize = f.size()
    hash = filesize
    
    if filesize < 65536 * 2:
        return "SizeError"
    
    buffer = f.read(65536)
    f.seek(max(0,filesize-65536),0)
    buffer += f.read(65536)
    f.close()
    for x in range((65536/bytesize)*2):
        size = x*bytesize
        (l_value,)= struct.unpack(longlongformat, buffer[size:size+bytesize])
        hash += l_value
        hash = hash & 0xFFFFFFFFFFFFFFFF
    
    returnHash = "%016x" % hash
    return filesize,returnHash


def OpensubtitlesHashRar(firsrarfile):
    log( __name__,"Hash Rar file")
    f = xbmcvfs.File(firsrarfile)
    a=f.read(4)
    if a!='Rar!':
        raise Exception('ERROR: This is not rar file.')
    seek=0
    for i in range(4):
        f.seek(max(0,seek),0)
        a=f.read(100)        
        type,flag,size=struct.unpack( '<BHH', a[2:2+5]) 
        if 0x74==type:
            if 0x30!=struct.unpack( '<B', a[25:25+1])[0]:
                raise Exception('Bad compression method! Work only for "store".')            
            s_partiizebodystart=seek+size
            s_partiizebody,s_unpacksize=struct.unpack( '<II', a[7:7+2*4])
            if (flag & 0x0100):
                s_unpacksize=(struct.unpack( '<I', a[36:36+4])[0] <<32 )+s_unpacksize
                log( __name__ , 'Hash untested for files biger that 2gb. May work or may generate bad hash.')
            lastrarfile=getlastsplit(firsrarfile,(s_unpacksize-1)/s_partiizebody)
            hash=addfilehash(firsrarfile,s_unpacksize,s_partiizebodystart)
            hash=addfilehash(lastrarfile,hash,(s_unpacksize%s_partiizebody)+s_partiizebodystart-65536)
            f.close()
            return (s_unpacksize,"%016x" % hash )
        seek+=size
    raise Exception('ERROR: Not Body part in rar file.')

def getlastsplit(firsrarfile,x):
    if firsrarfile[-3:]=='001':
        return firsrarfile[:-3]+('%03d' %(x+1))
    if firsrarfile[-11:-6]=='.part':
        return firsrarfile[0:-6]+('%02d' % (x+1))+firsrarfile[-4:]
    if firsrarfile[-10:-5]=='.part':
        return firsrarfile[0:-5]+('%1d' % (x+1))+firsrarfile[-4:]
    return firsrarfile[0:-2]+('%02d' %(x-1) )

def addfilehash(name,hash,seek):
    f = xbmcvfs.File(name)
    f.seek(max(0,seek),0)
    for i in range(8192):
        hash+=struct.unpack('<q', f.read(8))[0]
        hash =hash & 0xffffffffffffffff
    f.close()    
    return hash

def normalizeString(_str):
    return unicodedata.normalize('NFKD', _str).encode('ascii','ignore').decode('utf-8')
    #return _str
    #return unicodedata.normalize('NFKD', _str)
    #return unicodedata.normalize('NFKD', _str).encode('ascii','ignore')
    #return unicodedata.normalize('NFKD', unicode(unicode(str, 'utf-8'))).encode('ascii','ignore')

def checkAndParseIfTitleIsTVshowEpisode(manualTitle):
    try:
        pattern = re.compile(r"%20|_|-|\+|\.")
        replaceWith = " "
        manualTitle = re.sub(pattern, replaceWith, manualTitle)

        matchShow = re.search(r'(?i)^(.*?)\sS\d', manualTitle)
        if matchShow == None:
            return ["NotTVShowEpisode", "0", "0",'']
        else:
            tempShow = matchShow.group(1)
        
        matchSnum = re.search(r'(?i)%s(.*?)E' %(tempShow+" s"), manualTitle)
        if matchSnum == None:
            return ["NotTVShowEpisode", "0", "0",'']
        else:
            tempSnum = matchSnum.group(1)
        
        matchEnum = re.search(r'(?i)%s(.*?)$' %(tempShow+" s"+tempSnum+"e"), manualTitle)
        if matchEnum == None:
            return ["NotTVShowEpisode", "0", "0",'']
        else:
            tempEnum = matchEnum.group(1)

        return [tempShow, tempSnum, tempEnum, 'episode']

    except Exception as err:
        log( __name__, "checkAndParseIfTitleIsTVshowEpisode error: '%s'" % err)                
        return ["NotTVShowEpisode", "0", "0",'']

def searchForIMDBID(query,item):  ##### burekas 
    import requests                       
    year=item["year"]
    info=(PTN.parse(query))
    tmdbKey = '653bb8af90162bd98fc7ee32bcbbfb3d'

    if item['tvshow'] and (item['dbtype'] == 'episode' or (item['season'] and item['episode'])):    
        type_search='tv'
        filename = 'subs.search.tmdb.%s.%s.%s.json'%(type_search,lowercase_with_underscores(query),year)
        url="https://api.tmdb.org/3/search/%s?api_key=%s&query=%s&language=en&append_to_response=external_ids"%(type_search,tmdbKey,quote_plus(item['tvshow']))
          #url="https://api.tmdb.org/3/search/tv?api_key=%s&query=%s&year=%s&language=he&append_to_response=external_ids"%(tmdbKey,quote_plus(item['tvshow']),year)
          
          #url='https://www.omdbapi.com/?apikey=8e4dcdac&t=%s&year=%s'%(item["tvshow"],item["year"])

        #json_results = get_TMDB_data_popularity_and_votes_sorted(url,filename)
        json_results = get_TMDB_data_filtered(url,filename,item['tvshow'],type_search)

        try:    tmdb_id = int(json_results[0]["id"])
        except Exception as e:
            log( "[Exception searchForIMDBID - tvshow - tmdb_id - %s]" % (e,))
            return 0        

        filename = 'subs.search.tmdb.fulldata.%s.%s.json'%(type_search,tmdb_id)
        url = "https://api.tmdb.org/3/%s/%s?api_key=%s&language=en&append_to_response=external_ids"%(type_search,tmdb_id,tmdbKey)
        log( __name__ , "searchTMDB fulldata id: %s" % url)
        json = caching_json(filename,url)
        
        try:    imdb_id = json['external_ids']["imdb_id"]
        except Exception as e:    
            log( "[Exception searchForIMDBID - tvshow - imdb_id - %s]" % (e,))
            return 0        
                  
        return imdb_id
   
    elif info['title']: # and item['dbtype'] == 'movie':
        type_search='movie'
        filename = 'subs.search.tmdb.%s.%s.%s.json'%(type_search,lowercase_with_underscores(query),year)
        if int(year) > 0:
            url = "https://api.tmdb.org/3/search/%s?api_key=%s&query=%s&year=%s&language=en"%(type_search,tmdbKey,quote(info['title']),year)
        else:
            url = "https://api.tmdb.org/3/search/%s?api_key=%s&query=%s&language=en"%(type_search,tmdbKey,quote(info['title']))
                               
        #json_results = get_TMDB_data_popularity_and_votes_sorted(url,filename)
        json_results = get_TMDB_data_filtered(url,filename,item['title'],type_search)

        try:    tmdb_id = int(json_results[0]["id"])
        except Exception as e:
            log( "[Exception searchForIMDBID - movie - tmdb_id - %s]" % (e,))
            return 0

        filename = 'subs.search.tmdb.fulldata.%s.%s.json'%(type_search,tmdb_id)
        url = "https://api.tmdb.org/3/%s/%s?api_key=%s&language=en&append_to_response=external_ids"%(type_search,tmdb_id,tmdbKey)
        log( __name__ , "searchTMDB fulldata id: %s" % url)        
        json = caching_json(filename,url)
        
        try:    imdb_id = json['external_ids']["imdb_id"]
        except Exception as e:
            log( "[Exception searchForIMDBID - movie - imdb_id - %s]" % (e,))
            return 0

        return imdb_id      

def get_TMDB_data_popularity_and_votes_sorted(url,filename):    ##### burekas
    log( __name__ , "searchTMDB: %s" % url)
    json = caching_json(filename,url)
    json_results = json["results"]
    log( __name__ , "searchTMDB: json_results - " + repr(json_results))
    json_results.sort(key = lambda x:x["popularity"], reverse=True)
    json_results.sort(key = lambda x:x["vote_count"], reverse=True)
    log( __name__ , "searchTMDB: json_results sorted - " + repr(json_results))

    return json_results
    
def get_TMDB_data_filtered(url,filename,query,type):    ##### burekas
    log( __name__ , "searchTMDB: %s" % url)
    log( __name__ , "query filtered: %s" % query)
    json = caching_json(filename,url)
    json_results = json["results"]
    log( __name__ , "searchTMDB: json_results - " + repr(json_results))
    if type=='tv':
        json_results.sort(key = lambda x:x["name"]==query, reverse=True)
    else:
        json_results.sort(key = lambda x:x["title"]==query, reverse=True)
    log( __name__ , "searchTMDB: json_results sorted - " + repr(json_results))

    return json_results     
      
def caching_json(filename, url):   ####### burekas
    import requests

    if (__addon__.getSetting( "json_cache" ) == "true"):
        json_file = path.join(__temp__, filename)    
        if not path.exists(json_file) or not path.getsize(json_file) > 20 or (time()-path.getmtime(json_file) > 30*60):
            data = requests.get(url, verify=False)
            open(json_file, 'wb').write(data.content)
        if path.exists(json_file) and path.getsize(json_file) > 20:
            with open(json_file,'r',encoding='utf-8') as json_data:
                json_object = load(json_data)
            return json_object
        else:
            return 0

    else:
        try:
          json_object = requests.get(url).json()
        except:
          json_object = {}
          pass
        return json_object           

def get_now_played():
    """
    Get info about the currently played file via JSON-RPC

    :return: currently played item's data
    :rtype: dict
    """
    request = dumps({
        'jsonrpc': '2.0',
        'method': 'Player.GetItem',
        'params': {
            'playerid': 1,
            'properties': ['showtitle', 'season', 'episode']
         },
        'id': '1'
    })
    item = loads(xbmc.executeJSONRPC(request))['result']['item']
    item['file'] = xbmc.Player().getPlayingFile()  # It provides more correct result
    return item

def get_more_data(filename):
    title, year = xbmc.getCleanMovieTitle(filename)
    log( __name__ , "CleanMovieTitle: title - %s, year - %s " %(title, year)) 
    tvshow=' '
    season=0
    episode=0
    try:
        yearval = int(year)
    except ValueError:
        yearval = 0
        
    patterns = [
                '\WS(?P<season>\d\d)E(?P<episode>\d\d)',
                '\W(?P<season1>\d)x(?P<episode1>\d\d)'
                ]
                
    for pattern in patterns:
        pattern = r'%s' % pattern
        match = re.search(pattern, filename, flags=re.IGNORECASE)
        log( __name__ , "regex match: " + repr(match)) 

        if match is None:
            continue
        else:
            title = title[:match.start('season') - 1].strip()
            season = match.group('season').lstrip('0')
            episode = match.group('episode').lstrip('0')
            log( __name__ , "regex parse: title = %s , season = %s, episode = %s " %(title,season,episode))
            return title,yearval,season,episode
    
    return title,yearval,season,episode 

def is_local_file_tvshow(item):
    return item["title"] and item["year"]==0

def lowercase_with_underscores(_str):
    return unicodedata.normalize('NFKD', _str).encode('utf-8','ignore').decode('utf-8')
    #return unicodedata.normalize('NFKD', (str)).encode('utf-8', 'ignore')    
