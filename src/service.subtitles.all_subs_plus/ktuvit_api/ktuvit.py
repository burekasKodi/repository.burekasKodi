import xbmcaddon
import json, re
import cache
import requests
from myLogger import myLogger

def GetKtuvitJson(item,imdb_id,prefix_ktuvit,color_ktuvit):
    response,f_id = get_ktuvit_data(item,imdb_id)

    subtitle_list,m_pre = parse_ktuvit_response(response,f_id,prefix_ktuvit,color_ktuvit)

    return subtitle_list,m_pre

def get_login_cook():
    __addon__ = xbmcaddon.Addon()

    headers = {
    'authority': 'www.ktuvit.me',
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'x-requested-with': 'XMLHttpRequest',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
    'content-type': 'application/json',
    'origin': 'https://www.ktuvit.me',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',

    'accept-language': 'en-US,en;q=0.9',

    }

    ktEmail = __addon__.getSetting( "KT_email" )
    if (__addon__.getSetting( "KT_email" ) == ''):
        ktEmail = "hatzel6969@gmail.com"

    ktEncPass = __addon__.getSetting( "KT_enc_pass" )
    if (__addon__.getSetting( "KT_enc_pass" ) == ''):
        ktEncPass = "Jw1n9nPOZRAHw9aVdarvjMph2L85pKGx79oAAFTCsaE="

    data = '{"request":{"Email":"%s","Password":"%s"}}' %(ktEmail, ktEncPass)

    login_cook = requests.post('https://www.ktuvit.me/Services/MembershipService.svc/Login', headers=headers, data=data).cookies
    login_cook_fix={}
    for cookie in login_cook:
        login_cook_fix[cookie.name]=cookie.value
    return login_cook_fix

def get_ktuvit_data(item,imdb_id):
    from service import is_local_file_tvshow

    regexHelper = re.compile('\W+', re.UNICODE)

    login_cook=cache.get(get_login_cook,1, table='subs')

    if item["tvshow"]:
        s_type='1'
        s_title=item["tvshow"]
    elif is_local_file_tvshow(item):
        s_type='1'
        s_title=item["title"]
    else:
        s_type='0'
        s_title=item["title"]

    headers = {
        'authority': 'www.ktuvit.me',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
        'content-type': 'application/json',
        'origin': 'https://www.ktuvit.me',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.ktuvit.me/Search.aspx',
        'accept-language': 'en-US,en;q=0.9',

    }

    data = '{"request":{"FilmName":"%s","Actors":[],"Studios":null,"Directors":[],"Genres":[],"Countries":[],"Languages":[],"Year":"","Rating":[],"Page":1,"SearchType":"%s","WithSubsOnly":false}}'%(s_title,s_type)

    response = requests.post('https://www.ktuvit.me/Services/ContentProvider.svc/SearchPage_search', headers=headers, data=data).json()

    j_data=json.loads(response['d'])['Films']
    f_id=''

    myLogger('Ktuvit data: ' + repr(data))
    myLogger('Ktuvit response: ' + repr(response))
    myLogger('Ktuvit j_data: ' + repr(j_data))

    #first filtered by imdb
    for itt in j_data:
        if imdb_id==itt['ImdbID']:
            f_id=itt['ID']

    #if ids still empty (wrong imdb on ktuvit page) filtered by text
    if f_id == '':
        s_title = regexHelper.sub('', s_title).lower()
        for itt in j_data:
            eng_name = regexHelper.sub('', regexHelper.sub(' ', itt['EngName'])).lower()
            heb_name = regexHelper.sub('', itt['HebName'])

            if (s_title.startswith(eng_name) or eng_name.startswith(s_title) or
                    s_title.startswith(heb_name) or heb_name.startswith(s_title)):
                f_id=itt["ID"]

    if f_id!='':
        url='https://www.ktuvit.me/MovieInfo.aspx?ID='+f_id


    if item["tvshow"] or is_local_file_tvshow(item):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0',
            'Accept': 'text/html, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Referer': url,
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'TE': 'Trailers',
        }

        params = (
            ('moduleName', 'SubtitlesList'),
            ('SeriesID', f_id),
            ('Season', item["season"]),
            ('Episode', item["episode"]),
        )

        response = requests.get('https://www.ktuvit.me/Services/GetModuleAjax.ashx', headers=headers, params=params, cookies=login_cook).content
    else:
        headers = {
            'authority': 'www.ktuvit.me',
            'cache-control': 'max-age=0',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'sec-fetch-dest': 'document',
            'referer': 'https://www.ktuvit.me/MovieInfo.aspx?ID='+f_id,
            'accept-language': 'en-US,en;q=0.9',

        }
        params = (
            ('ID', f_id),
        )

        response = requests.get('https://www.ktuvit.me/MovieInfo.aspx', headers=headers, params=params, cookies=login_cook).content

    return response,f_id

def parse_ktuvit_response(response,f_id,prefix_ktuvit,color_ktuvit):
    MyScriptID = xbmcaddon.Addon().getAddonInfo('id')

    regex='<tr>(.+?)</tr>'
    m_pre=re.compile(regex,re.DOTALL).findall(response.decode('utf-8'))
    #z=1
    subtitle=' '
    subtitle_list=[]

    for itt in m_pre:
        regex='<div style="float.+?>(.+?)<br />.+?data-subtitle-id="(.+?)"'
        m=re.compile(regex,re.DOTALL).findall(itt)
        if len(m)==0:
            continue

        if ('i class' in m[0][0]):    #burekas fix for KT titles
            regex='כתובית מתוקנת\'></i>(.+?)$'
            n=re.compile(regex,re.DOTALL).findall(m[0][0])
            nm=n[0].replace('\n','').replace('\r','').replace('\t','').replace(' ','')
        else:
            nm=m[0][0].replace('\n','').replace('\r','').replace('\t','').replace(' ','')

        data='{"request":{"FilmID":"%s","SubtitleID":"%s","FontSize":0,"FontColor":"","PredefinedLayout":-1}}'%(f_id,m[0][1])

        nlabel = "Hebrew"
        nlabel2 = '[COLOR '+color_ktuvit+']'+nm+'[/COLOR]'
        #nlabel2 = '[COLOR '+color_ktuvit+']'+prefix_ktuvit+' '+nm+'[/COLOR]'
        #nlabel2 = '[COLOR '+color_ktuvit+']'+str(z)+'. '+prefix_ktuvit+' '+nm+'[/COLOR]'
        nicon = '[COLOR '+color_ktuvit+']'+prefix_ktuvit+'[/COLOR]'
        nthumb = "he"
        url = "plugin://%s/?action=download&versioname=%s&id=%s&source=%s&language=%s&thumbLang=%s" % (MyScriptID,
                                                                              nm,
                                                                              "ktuvit$$$"+data+'$$$'+f_id,
                                                                              'ktuvit',
                                                                              nlabel,
                                                                              nthumb)

        json_data={'url':url,
                            'label':nlabel,
                            'label2':nlabel2,
                            'iconImage':nicon,
                            'thumbnailImage':nthumb,
                            'hearing_imp':'false',
                            'sync': 'false'}

        subtitle_list.append(json_data)
        #z=z+1

    return subtitle_list,m_pre

def ktuvit_download_sub(id,MySubFolder,mode_subtitle):
    from os import path

    #font_c="0"
    #size=0

    o_id=id
    id=id.split("$$$")[1].split("$$$")[0]
    login_cook=cache.get(get_login_cook,1, table='subs')

    f_id=o_id.split("$$$")[2]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.ktuvit.me',
        'Connection': 'keep-alive',
        'Referer': 'https://www.ktuvit.me/MovieInfo.aspx?ID='+f_id,
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
    }

    data = id
    response = requests.post('https://www.ktuvit.me/Services/ContentProvider.svc/RequestSubtitleDownload', headers=headers, cookies=login_cook, data=data).json()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Referer': 'https://www.ktuvit.me/MovieInfo.aspx?ID='+f_id,
        'Upgrade-Insecure-Requests': '1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
    }

    params = (
        ('DownloadIdentifier', json.loads(response['d'])['DownloadIdentifier']),
    )

    response = requests.get('https://www.ktuvit.me/Services/DownloadFile.ashx', headers=headers, params=params, cookies=login_cook)
    headers=(response.headers)

    file_name=headers['Content-Disposition'].split("filename=")[1]
    archive_file = path.join(MySubFolder, file_name)

    # Throw an error for bad status codes
    response.raise_for_status()

    subtitle_list=[]
    with open(archive_file, 'wb') as handle:
        for block in response.iter_content(1024):
            handle.write(block)

    subtitle_list.append(archive_file)

    if mode_subtitle>1:
        return subtitle_list," "
    else:
        return subtitle_list,True
