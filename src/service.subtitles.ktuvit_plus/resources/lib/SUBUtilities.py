# -*- coding: utf-8 -*-
import os
import re
import unicodedata
import json
import zlib
import shutil

import xbmc
import xbmcvfs
import xbmcaddon
from bs4 import BeautifulSoup

from http.cookiejar import LWPCookieJar
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode, quote, quote_plus

##### burekas fix
import PTN
from os import path
from json import loads, load
from time import time

__addon__ = xbmcaddon.Addon()
__version__ = __addon__.getAddonInfo('version')  # Module version
__scriptname__ = __addon__.getAddonInfo('name')
__language__ = __addon__.getLocalizedString
__profile__ = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))
__temp__ = xbmcvfs.translatePath(os.path.join(__profile__, 'temp', ''))
__subsFolder__ = xbmcvfs.translatePath(os.path.join(__temp__, 'subs', ''))
__kodi_version__ = xbmc.getInfoLabel('System.BuildVersion').split(' ')[0]

regexHelper = re.compile('\W+', re.UNICODE)


# ===============================================================================
# Private utility functions
# ===============================================================================
def normalizeString(_str):
    if not isinstance(_str, str):
        _str = unicodedata.normalize('NFKD', _str)  # .encode('utf-8', 'ignore')
    return _str


def clean_title(item):
    title = os.path.splitext(os.path.basename(item["title"]))
    tvshow = os.path.splitext(os.path.basename(item["tvshow"]))

    if len(title) > 1:
        if re.match(r'^\.[a-z]{2,4}$', title[1], re.IGNORECASE):
            item["title"] = title[0]
        else:
            item["title"] = ''.join(title)
    else:
        item["title"] = title[0]

    if len(tvshow) > 1:
        if re.match(r'^\.[a-z]{2,4}$', tvshow[1], re.IGNORECASE):
            item["tvshow"] = tvshow[0]
        else:
            item["tvshow"] = ''.join(tvshow)
    else:
        item["tvshow"] = tvshow[0]

    # Removes country identifier at the end
    item['title'] = re.sub(r'\([^\)]+\)\W*$', '', item['title']).strip()
    item['tvshow'] = re.sub(r'\([^\)]+\)\W*$', '', item['tvshow']).strip()


def parse_rls_title(item): ##### burekas
    title = re.sub(r'\([^\)]+\)\W*$', '', item['title']).strip()
    tvshow = re.sub(r'\([^\)]+\)\W*$', '', item['tvshow']).strip()

    groups = re.findall(r"(.*?) (\d{4})? ?(?:s|season|)(\d{1,2})(?:e|episode|x|\n)(\d{1,2})", title, re.I)

    if len(groups) == 0:
        groups = re.findall(r"(.*?) (\d{4})? ?(?:s|season|)(\d{1,2})(?:e|episode|x|\n)(\d{1,2})", tvshow, re.I)

    if len(groups) > 0 and len(groups[0]) >= 3:
        title, year, season, episode = groups[0]
        item["year"] = str(int(year)) if len(year) == 4 else year

        item["tvshow"] = re.sub(r'\([^\)]+\)\W*$', '', title).strip()
        item["season"] = str(int(season))
        item["episode"] = str(int(episode))
        log("TV Parsed Item: %s" % (item,))

    else:  # For cases such a movie: "1917"
        groups = re.findall(r"(.*?)(\d{4})", item["title"], re.I)
        if len(groups) > 0 and len(groups[0]) >= 1:
            if len(groups[0][0]) >= 1:
                title = groups[0][0]
                item["title"] = re.sub(r'\([^\)]+\)\W*$', '', title).strip()
                item["year"] = groups[0][1] if len(groups[0]) == 2 else item["year"]
                
                log("MOVIE Parsed Item: %s" % (item,))
            elif len(groups[0][1]) >= 1:
                title = groups[0][1]
                item["title"] = re.sub(r'\([^\)]+\)\W*$', '', title).strip()
                item["year"] = groups[1][1] if len(groups[1]) == 2 else item["year"]
                
                log("MOVIE Parsed Item: %s" % (item,))


def log(msg):
    xbmc.log("### [%s] - %s" % (__scriptname__, msg), level=xbmc.LOGDEBUG)


def notify(msg_id):
    xbmc.executebuiltin((u'Notification(%s,%s)' % (__scriptname__, __language__(msg_id))))


class SubsHelper:
    BASE_URL = "https://www.ktuvit.me/Services"

    def __init__(self):
        self.urlHandler = URLHandler()

    def get_subtitle_list(self, item):
        search_results = self._search(item)
        results = self._build_subtitle_list(search_results, item)

        return results

    # return list of movies / tv-series from the site`s search
    def _search(self, item):
        search_string = re.split(r'\s\(\w+\)$', item["tvshow"])[0] if item["tvshow"] else item["title"]
        log("search_string: %s" % search_string)

        query = {"FilmName": search_string,
                 "Actors": [],
                 "Studios": None,
                 "Directors": [],
                 "Genres": [],
                 "Countries": [],
                 "Languages": [],
                 "Year": "",
                 "Rating": [],
                 "Page": 1,
                 "SearchType": "0",
                 "WithSubsOnly": False}
        if item["tvshow"]:
            query["SearchType"] = "1"
        elif item["year"]:
            query["Year"] = item["year"]

        search_result = self.urlHandler.request(self.BASE_URL + "/ContentProvider.svc/SearchPage_search",
                                                data={"request": query})

        results = []
        log("Results: %s" % search_result)

        if search_result is None or len(search_result["Films"]) == 0:
            #notify(32001)
            return results  # return empty set

        ids = self._get_filtered_ids(search_result["Films"], search_string, item)  ##### burekas
        log("Filtered Ids: %s" % ids)

        if item["tvshow"]:
            results = self._search_tvshow(item, ids)
        else:
            results = self._search_movie(ids)

        log("Subtitles: %s" % results)

        return results

    def _search_tvshow(self, item, ids):
        subs = []

        for id in ids:
            query_string = {
                "moduleName": "SubtitlesList",
                "SeriesID": id,
                "Season": item['season'],
                "Episode": item['episode']
            }
            raw_html = self.urlHandler.request(self.BASE_URL + "/GetModuleAjax.ashx", query_string=query_string)

            sub_list = BeautifulSoup(raw_html, "html.parser")
            sub_rows = sub_list.find_all("tr")

            for row in sub_rows:
                columns = row.find_all("td")
                sub = {
                    'id': id
                }
                for index, column in enumerate(columns):
                    if index == 0:
                        sub['rls'] = column.get_text().strip().split("\n")[0]
                    if index == 4:
                        sub['downloads'] = int(column.get_text().strip())
                    if index == 5:
                        sub['sub_id'] = column.find("input", attrs={"data-sub-id": True})["data-sub-id"]

                if (sub['rls'] != 'אין כתוביות'): ###### burekas fix (Sometimes a strange result returns as 'אין כתוביות')  
                    subs.append(sub)

        return subs

    def _search_movie(self, ids):
        subs = []

        for movie_id in ids:
            query_string = {
                "ID": movie_id,
            }
            raw_html = self.urlHandler.request(self.BASE_URL + "/../MovieInfo.aspx", query_string=query_string)
            html = BeautifulSoup(raw_html, "html.parser")
            sub_rows = html.select("table#subtitlesList tbody > tr")
            #log('html %s' % sub_rows)

            for row in sub_rows:
                columns = row.find_all("td")
                sub = {
                    'id': movie_id
                }
                for index, column in enumerate(columns):
                    if index == 0:
                        sub['rls'] = column.get_text().strip().split("\n")[0]
                    if index == 4:
                        sub['downloads'] = int(column.get_text().strip())
                    if index == 5:
                        sub['sub_id'] = column.find("a", attrs={"data-subtitle-id": True})["data-subtitle-id"]

                if (sub['rls'] != 'אין כתוביות'): ###### burekas fix (Sometimes a strange result returns as 'אין כתוביות')  
                    subs.append(sub)

        return subs

    def _build_subtitle_list(self, search_results, item):
        language = 'en' if item["preferredlanguage"]=='eng' else 'he' #'he'
        lang3 = xbmc.convertLanguage(language, xbmc.ISO_639_2)
        total_downloads = 0
        ret = []
        for result in search_results:
            title = result["rls"]
            subtitle_rate = self._calc_rating(title, item["file_original_path"])
            total_downloads += result['downloads']

            ret.append({
                'lang_index': exec('try:item["3let_language"].index(lang3)\nexcept:0'), #item["3let_language"].index(lang3),
                'filename': title,
                'language_name': xbmc.convertLanguage(language, xbmc.ENGLISH_NAME),
                'language_flag': language,
                'id': result["id"],
                'sub_id': result["sub_id"],
                'rating': result['downloads'],
                'sync': subtitle_rate >= 3.8,
                'hearing_imp': False,
                'is_preferred': lang3 == item['preferredlanguage']
            })

        # Fix the rating
        if total_downloads:
            for it in ret:
                log('rating %s totals %s' % (it['rating'], total_downloads))
                it["rating"] = str(int(round(it["rating"] / float(total_downloads), 1) * 5))

        return sorted(ret, key=lambda x: (x['is_preferred'], x['lang_index'], x['sync'], x['rating']), reverse=True)

    def _calc_rating(self, subsfile, file_original_path):
        file_name = os.path.basename(file_original_path)
        folder_name = os.path.split(os.path.dirname(file_original_path))[-1]

        subsfile = re.sub(r'\W+', '.', subsfile).lower()
        file_name = re.sub(r'\W+', '.', file_name).lower()
        folder_name = re.sub(r'\W+', '.', folder_name).lower()
        log("# Comparing Releases:\n [subtitle-rls] %s \n [filename-rls] %s \n [folder-rls] %s" % (
            subsfile, file_name, folder_name))

        subsfile = subsfile.split('.')
        file_name = file_name.split('.')[:-1]
        folder_name = folder_name.split('.')

        if len(file_name) > len(folder_name):
            diff_file = list(set(file_name) - set(subsfile))
            rating = (1 - (len(diff_file) / float(len(file_name)))) * 5
        else:
            diff_folder = list(set(folder_name) - set(subsfile))
            rating = (1 - (len(diff_folder) / float(len(folder_name)))) * 5

        log("\n rating: %f (by %s)" % (round(rating, 1), "file" if len(file_name) > len(folder_name) else "folder"))

        return round(rating, 1)

    def download(self, id, sub_id, filename):
        ## Cleanup temp dir, we recomend you download/unzip your subs in temp folder and
        ## pass that to XBMC to copy and activate
        if xbmcvfs.exists(__subsFolder__):
            shutil.rmtree(__subsFolder__)
        xbmcvfs.mkdirs(__subsFolder__)

        query = {
            "request": {
                "FilmID": id,
                "SubtitleID": sub_id,
                "FontSize": 0,
                "FontColor": "",
                "PredefinedLayout": -1}}

        response = self.urlHandler.request(self.BASE_URL + "/ContentProvider.svc/RequestSubtitleDownload", data=query)
        f = self.urlHandler.request(self.BASE_URL + '/DownloadFile.ashx',
                                    query_string={"DownloadIdentifier": response["DownloadIdentifier"]})
        with open(filename, "wb") as subFile:
            subFile.write(f)
        subFile.close()

    def login(self, notify_success=False):
        email = __addon__.getSetting("email")
        password = __addon__.getSetting("password")
        post_data = {"request": {"Email": email, "Password": password}}

        response = self.urlHandler.request(self.BASE_URL + "/MembershipService.svc/Login", data=post_data)
        log("Login response is: %s" % (response))

        if response["IsSuccess"] is True:
            self.urlHandler.save_cookie()
            if notify_success:
                notify(32007)
            return True
        else:
            notify(32005)
            return None

    def _get_filtered_ids(self, list, search_string, item):    ##### burekas
        ids = []

        search_string = regexHelper.sub('', search_string).lower()

        #first filtered by imdb
        for result in list:
            if (result['ImdbID'] == item['imdb_id']):
                ids.append(result["ID"])

        #if ids still empty (wrong imdb on ktuvit page) filtered by text
        if ids == []:
            for result in list:
                eng_name = regexHelper.sub('', regexHelper.sub(' ', result['EngName'])).lower()
                heb_name = regexHelper.sub('', result['HebName'])

                if (search_string.startswith(eng_name) or eng_name.startswith(search_string) or
                        search_string.startswith(heb_name) or heb_name.startswith(search_string)):
                    ids.append(result["ID"])            

        return ids


class URLHandler:
    def __init__(self):
        cookie_filename = os.path.join(__profile__, "cookiejar.txt")
        self.cookie_jar = LWPCookieJar(cookie_filename)
        if os.access(cookie_filename, os.F_OK):
            self.cookie_jar.load()

        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [('Accept-Encoding', 'gzip'),
                                  ('Accept-Language', 'en-us,en;q=0.5'),
                                  ('Pragma', 'no-cache'),
                                  ('Cache-Control', 'no-cache'),
                                  ('Content-type', 'application/json'),
                                  ('User-Agent',
                                   'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Kodi/%s Chrome/78.0.3904.97 Safari/537.36' % (
                                       __kodi_version__))]

    def request(self, url, data=None, query_string=None, referrer=None, cookie=None):
        if data is not None:
            data = json.dumps(data).encode('utf8')
        if query_string is not None:
            url += '?' + urlencode(query_string)
        if referrer is not None:
            self.opener.addheaders += [('Referrer', referrer)]
        if cookie is not None:
            self.opener.addheaders += [('Cookie', cookie)]

        content = None
        log("Getting url: %s" % (url))
        if data is not None:
            log("Post Data: %s" % (data))
        try:
            req = Request(url, data, headers={'Content-Type': 'application/json'})
            response = self.opener.open(req)
            content = None if response.code != 200 else response.read()

            if response.headers.get('content-encoding', '') == 'gzip':
                try:
                    content = zlib.decompress(content, 16 + zlib.MAX_WBITS)
                except zlib.error:
                    pass

            if response.headers.get('content-type', '').startswith('application/json'):
                try:
                    parsed_content = json.loads(content)
                    content = json.loads(parsed_content["d"])
                    log("content (without encoding) is: %s" % (content))                   
                except:
                    parsed_content = json.loads(content, encoding="utf-8")
                    content = json.loads(parsed_content["d"], encoding="utf-8")
                    log("content (with encoding) is: %s" % (content))

            response.close()
        except Exception as e:
            log("Failed to get url: %s\n%s" % (url, e))
            # Second parameter is the filename
        return content

    def save_cookie(self):
        # extend cookie expiration
        for cookie in self.cookie_jar:
            if cookie.expires is not None:
                cookie.expires += 2 * 12 * 30 * 24 * 60 * 60

        self.cookie_jar.save()

''' ###### burekas
def title_from_focused_item(item_data): ###### burekas
    label_type = xbmc.getInfoLabel("ListItem.DBTYPE")  # movie/tvshow/season/episode
    label_movie_title = xbmc.getInfoLabel("ListItem.OriginalTitle")
    is_movie = xbmc.getCondVisibility("Container.Content(movies)") or label_type == 'movie'
    is_episode = xbmc.getCondVisibility("Container.Content(episodes)") or label_type == 'episode'

    title = ''
    if is_movie and label_movie_title and item_data['year']:
        title = label_movie_title + " " + item_data['year']
    elif is_episode and item_data['tvshow'] and item_data['season'] and item_data['episode']:
        title = ("%s S%.2dE%.2d" % (item_data['tvshow'], int(item_data['season']), int(item_data['episode'])))

    return title
'''

def get_TMDB_data_popularity_and_votes_sorted(url,filename):    ##### burekas
    log("searchTMDB: %s" % url)
    json = cachingJSON(filename,url)
    json_results = json["results"]
    log("searchTMDB: json_results - " + repr(json_results))
    json_results.sort(key = lambda x:x["popularity"], reverse=True)
    json_results.sort(key = lambda x:x["vote_count"], reverse=True)
    log("searchTMDB: json_results sorted - " + repr(json_results))

    return json_results
    
def get_TMDB_data_filtered(url,filename,query,type):    ##### burekas
    log("searchTMDB: %s" % url)
    log("query filtered: %s" % query)
    json = cachingJSON(filename,url)
    json_results = json["results"]
    log("searchTMDB: json_results - " + repr(json_results))
    if type=='tv':
        json_results.sort(key = lambda x:x["name"]==query, reverse=True)
    else:
        json_results.sort(key = lambda x:x["title"]==query, reverse=True)
    log("searchTMDB: json_results sorted - " + repr(json_results))

    return json_results      

def getOriginalTitle(): ###### burekas

    if xbmc.getInfoLabel("VideoPlayer.TVshowtitle").isascii():
        return normalizeString(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))  # Show

    #First, check if database has the original title.
    labelTVShowTitle = getTVshowOriginalTitleByJSONandDBid("playing")    ##using kodi database json
    #If not, try get the original title by using tmdb api
    if (labelTVShowTitle == "" or not labelTVShowTitle.isascii()):
        labelTVShowTitle = getTVshowOriginalTitleByTMDBapi("playing")  ##New way using tmdb api

    return labelTVShowTitle
	
def takeTitleFromFocusedItem(type="movie"): ###### burekas
    labelMovieTitle = xbmc.getInfoLabel("ListItem.OriginalTitle")
    labelYear = xbmc.getInfoLabel("ListItem.Year")
    labelTVShowTitle = xbmc.getInfoLabel("ListItem.TVShowTitle") #xbmc.getInfoLabel("ListItem.OriginalTitle")
    labelSeason = xbmc.getInfoLabel("ListItem.Season")
    labelEpisode = xbmc.getInfoLabel("ListItem.Episode")
    labelType = xbmc.getInfoLabel("ListItem.DBTYPE")  #movie/tvshow/season/episode	
    isItMovie = labelType == 'movie' or xbmc.getCondVisibility("Container.Content(movies)")
    isItEpisode = labelType == 'episode' or xbmc.getCondVisibility("Container.Content(episodes)")
    labelDBID = xbmc.getInfoLabel("ListItem.DBID")

    #If item is TVShow and in the library => When titles are not in english
    if isItEpisode and type == 'tvshow' and labelDBID != "":
        #First, check if database has the original title.
        labelTVShowTitle = getTVshowOriginalTitleByJSONandDBid('notPlaying')    ##using kodi database json
        #If not, try get the original title by using tmdb api
        if (labelTVShowTitle == "" or not labelTVShowTitle.isascii()):
            labelTVShowTitle = getTVshowOriginalTitleByTMDBapi('notPlaying')  ##New way using tmdb api          

    title = 'SearchFor...'
    if isItMovie and labelMovieTitle and labelYear:
        title = ("%s %s" % (labelMovieTitle, labelYear)) if type == 'movie' else '' ###### burekas
    elif isItEpisode and labelTVShowTitle and labelSeason and labelEpisode:
        title = ("%s S%.2dE%.2d" % (labelTVShowTitle, int(labelSeason), int(labelEpisode))) if type == 'tvshow' else '' ###### burekas

    return title

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
               
        tvshowOriginalTitle = resultsTVShowDetails["result"]["tvshowdetails"]["originaltitle"]
        
        originalShowTitle = tvshowOriginalTitle

        return originalShowTitle

    except Exception as err:
        log('Caught Exception: error getTVshowOriginalTitleByJSONandDBid: %s' % format(err))
        originalShowTitle = ''			
        return originalShowTitle 


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
        
        log("searchTMDB for original tv title: %s" % url)
        
        json_results = get_TMDB_data_popularity_and_votes_sorted(url,filename)
        
        '''
        json = cachingJSON(filename,url)

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
		'''
        
        try:    originalTitle = json_results[0]["name"]
        except:
            log( "[%s]" % (e,))
            return ''         
               
        return originalTitle
    
    except Exception as err:
        log('Caught Exception: error searchTMDB: %s' % format(err))
        originalTitle = ''		
        return originalTitle
        
def cachingJSON(filename, url):   ####### burekas
    from requests import get

    if (__addon__.getSetting( "json_cache" ) == "true"):
        json_file = path.join(__temp__, filename)
        if not path.exists(json_file) or not path.getsize(json_file) > 20 or (time()-path.getmtime(json_file) > 30*60):
            data = get(url, verify=False)
            open(json_file, 'wb').write(data.content)
        if path.exists(json_file) and path.getsize(json_file) > 20:
            with open(json_file,'r',encoding='utf-8') as json_data:
                json_object = load(json_data)
            return json_object
        else:
            return 0

    else:
        try:
          json_object = get(url).json()
        except:
          json_object = {}
          pass
        return json_object  

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
        log( "checkAndParseIfTitleIsTVshowEpisode error: '%s'" % err)                
        return ["NotTVShowEpisode", "0", "0",'']

def searchForIMDBID(query,item):  ##### burekas 
    import requests
    
    log("searchForIMDBID item: %s" %repr(item))

    #if item["year"]:
    year=item["year"]
    #else:
    #    year='0000'
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
        log("searchTMDB fulldata id: %s" % url)
        json = cachingJSON(filename,url)
        
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
        log("searchTMDB fulldata id: %s" % url)
        json = cachingJSON(filename,url)
        
        try:    imdb_id = json['external_ids']["imdb_id"]
        except Exception as e:
            log( "[Exception searchForIMDBID - movie - imdb_id - %s]" % (e,))
            return 0

        return imdb_id      

'''
def Caching(filename,url):
    import requests

    try:
      x=requests.get(url).json()
    except:
      x={}
      pass
    return x
'''    

def get_now_played():
    """
    Get info about the currently played file via JSON-RPC

    :return: currently played item's data
    :rtype: dict
    """
    request = json.dumps({
        'jsonrpc': '2.0',
        'method': 'Player.GetItem',
        'params': {
            'playerid': 1,
            'properties': ['showtitle', 'season', 'episode']
         },
        'id': '1'
    })
    item = json.loads(xbmc.executeJSONRPC(request))['result']['item']
    item['file'] = xbmc.Player().getPlayingFile()  # It provides more correct result
    return item

def get_more_data(filename):
    title, year = xbmc.getCleanMovieTitle(filename)
    log("CleanMovieTitle: title - %s, year - %s " %(title, year)) 
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
        log("regex match: " + repr(match)) 

        if match is None:
            continue
        else:
            title = title[:match.start('season') - 1].strip()
            season = match.group('season').lstrip('0')
            episode = match.group('episode').lstrip('0')
            log("regex parse: title = %s , season = %s, episode = %s " %(title,season,episode))
            return title,yearval,season,episode
    
    return title,yearval,season,episode 

def is_local_file_tvshow(item):
    return item["title"] and item["year"]==0
  
def lowercase_with_underscores(_str):   ####### burekas
    return unicodedata.normalize('NFKD', _str).encode('utf-8','ignore').decode('utf-8')
    #return normalize('NFKD', str(str(str, 'utf-8'))).encode('utf-8', 'ignore')