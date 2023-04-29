import xbmcaddon
import requests                     # requests.get
import os                           # os.path operations
from myLogger import logger         # logging utils

# def getDomainWizdom():
#     try:
#         myDomain = str(requests.get('https://pastebin.com/raw/1vbRPSGh').text)
#         return myDomain
#     except Exception as err:
#         myLogger('Caught Exception: error in finding getDomain: %s' % format(err))
#         return "wizdom.xyz" # "lolfw.com"

def get_wizdom_url():
    # return "http://" + getDomainWizdom() + "/api"
    return "http://wizdom.xyz/api"


def colored(color, msg):
    return '[COLOR ' + color + ']' + msg + '[/COLOR]'
    
def GetWizJson(imdb, prefix_wizdom, color_wizdom, season="0", episode="0", version="0"):

    # TODO: move json caching to its own file and include at the head of this
    # file (bad practice to include inside functions), for now: service.py
    # is using wizdom.py but not fully initialized when this is called
    from service import caching_json    # caching
    
    # for some reason, sometimes it is called with str and sometimes with int
    # for now force it as str
    # TODO: cleanup everywhere it is called with int or non-str
    season = str(season)
    episode = str(episode)
    version = str(version)
    
    logger.debug("imdb: %s, prefix_wizdom: %s, color_wizdom: %s" % (imdb, prefix_wizdom, color_wizdom))
    logger.debug("season: %s, episode: %s, version: %s" % (season, episode, version))

    MyScriptID = xbmcaddon.Addon().getAddonInfo('id')

    #old url was: http://json.wizdom.xyz/search.php
    #new url is: http://wizdom.xyz/search
    url = get_wizdom_url() + "/search?action=by_id"
    url += "&imdb=" + imdb
    url += "&season=" + season
    url += "&episode=" + episode
    url += "&version=" + version

    logger.debug("url: " + repr(url))

    filename = 'subs.search.wizdom.%s.%s.%s.json' % (imdb, season, episode)
    logger.debug("caching_json filename: " + filename)
    
    json_object = caching_json(filename, url)
    logger.debug("json_object = " + repr(json_object))
    
    subs_rate = []
    id_all_collection=[]
    subtitle_list=[]

    if 0 == (json_object):
        return subtitle_list, json_object

    for item_data in json_object:
    
        nlabel = "Hebrew"
        nlabel2 = colored(color_wizdom, item_data["versioname"])
        nicon = colored(color_wizdom, prefix_wizdom)
        nthumb = "he"

        _id = 'wizdom$$$' + str(item_data["id"])

        url = "plugin://%s/?action=download&versioname=%s&id=%s&source=%s&language=%s&thumbLang=%s" % (MyScriptID,
                                                                    item_data["versioname"],
                                                                    _id,
                                                                    'wizdom',
                                                                    nlabel,
                                                                    nthumb)
        logger.debug("item_data.url = " + url)
        
        json_data={'url':url,
                   'label' : nlabel,
                   'label2' : nlabel2,
                   'iconImage' : nicon,
                   'thumbnailImage' : nthumb,
                   'hearing_imp' : 'false',
                   'sync': 'true' if int(item_data["score"])>8 else 'false'}
        
        if item_data["id"] not in id_all_collection:
            logger.debug("append new item_id: " + str(item_data["id"]))
            
            id_all_collection.append(item_data["id"])

            subtitle_list.append(json_data)
            links_wizdom=subtitle_list

    return subtitle_list, json_object

def wizdom_download_sub(subid, filename):
    logger.debug("called wizdom_download_sub()")
    logger.debug("  - subid: " + subid)
    logger.debug("  - filename: " + filename)

    if not os.path.exists(filename):
        url = get_wizdom_url() + "/files/sub/" + subid
        data = requests.get(url)
        
        with open(filename, 'wb') as f:
            f.write(data.content)
    else:
        logger.debug("file exist: " + filename)
