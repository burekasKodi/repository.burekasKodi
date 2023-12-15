service.subtitles.ktuvit
=========================

Ktuvit.me subtitle service for Kodi

In order to get the encoded password:

1. Open "ktuvit.me" (https://www.ktuvit.me) in the browser
2. Open "developer tools" (https://developers.google.com/web/tools/chrome-devtools/open)  
(in Windows: ctrl+shift+c)
3. Enter this code in the **console**, replace these fields with your login details (MY-PASSWORD,MY@EMAIL.COM) and then execute: 

x = { value: 'MY-PASSWORD' };
loginHandler.EncryptPassword({}, x, 'MY@EMAIL.COM');
copy(x.value); // this will copy your encrtyped password to your clipboard
console.log(`Now past it in the addon's settings at the Encrypted password field`)
4. The encrypt code is now ready to paste it in kodi.

