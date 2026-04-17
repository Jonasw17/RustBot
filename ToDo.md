#### TODO:

\- camera pictures? (https://github.com/liamcottle/rustplus.js/blob/master/camera.js)

\- map jpeg for connection info (https://github.com/liamcottle/rustplus.js/blob/master/examples/5\_download\_map\_jpeg.js)



\- Maybe AI integration





#### TO FIX: 

##### 


```
{

&nbsp; "fcm\_credentials": {

&nbsp;   "gcm": {

&nbsp;     "androidId": "5441822150050427060",

&nbsp;     "securityToken": "3326182556565053449"

&nbsp;   },

&nbsp;   "fcm": {

&nbsp;     "token": "fZjCDeLTzSo:APA91bGklZAE0GCTz2LpWqR-reUpe\_3Q7uPG3gXIFlSDLW2uuV3WwUB2NMrDGyIAiiiac2VKLAqG5SRgh7lD8y51vD8zaH-VU5i-BljBXwEjiUE-zk4qW4c"

&nbsp;   }

&nbsp; },

&nbsp; "expo\_push\_token": "ExponentPushToken\[DYJE8WKUkQRuiPdxiKGf9L]",

&nbsp; "rustplus\_auth\_token": "eyJzdGVhbUlkIjoiNzY1NjExOTgxMjc5ODU5NTUiLCJ2ZXJzaW9uIjowLCJpc3MiOjE3NzYzNjk2NjksImV4cCI6MTc3NzU3OTI2OX0=.qoI1viElnm2/jFIPFNYSJQYoXrBfS1XbEYIXOO4snQEF5hH0KZ3JpYdZ+qu647P3T0WU4vziubdv2D9w92WuDQ=="

}
```

*Could not find Steam ID in the config file. Make sure you uploaded the correct rustplus.config.json

---
2026-04-16 21:56:51 \[INFO] RustBot: Starting Rust+ Companion Bot (Multi-User Architecture)...*

*2026-04-16 21:56:51 \[INFO] discord.client: logging in using static token*

*2026-04-16 21:56:54 \[INFO] discord.gateway: Shard ID None has connected to Gateway (Session ID: 499cfa34c8251ef75afd8f21487fc662).*

*2026-04-16 21:56:56 \[INFO] RustBot: Logged in as RustAI#4278 (ID: 1473369994556608694)*

*2026-04-16 21:56:56 \[INFO] RustBot: Channel configuration:*

*2026-04-16 21:56:56 \[INFO] RustBot:   Commands      →  #commands*

*2026-04-16 21:56:56 \[INFO] RustBot:   Notifications →  #notifications*

*2026-04-16 21:56:56 \[INFO] RustBot:   Chat relay    →  #teamchat*

*2026-04-16 21:56:56 \[INFO] RustBot: Clearing notification channel...*

*2026-04-16 21:56:56 \[INFO] RustBot: Cleared 1 message(s) from notification channel*

*2026-04-16 21:56:56 \[INFO] RustBot: Clearing command channel...*

*2026-04-16 21:56:56 \[INFO] RustBot: Cleared 0 message(s) from command channel*

*2026-04-16 21:56:56 \[INFO] RustBot: Clearing chat relay channel...*

*2026-04-16 21:56:57 \[INFO] RustBot: Cleared 0 message(s) from chat relay channel*

*2026-04-16 21:56:57 \[INFO] RustBot: Chat relay callback registered*

*2026-04-16 21:56:57 \[INFO] RustBot: Timer system started*

*2026-04-16 21:56:57 \[INFO] RustBot:  1 user(s) registered*

*2026-04-16 21:56:57 \[INFO] Timers: Timer loop started*

*2026-04-16 21:56:57 \[INFO] ServerManager: Starting FCM listeners for 1 user(s)*

*2026-04-16 21:56:57 \[INFO] ServerManager: \[FCM] Starting listener for denbompa (attempt 1)*

*2026-04-16 21:56:57 \[WARNING] ServerManager: \[FCM] Listener startup key error for denbompa (attempt 1): 'fcm\_credentials'*

*2026-04-16 21:56:57 \[INFO] ServerManager: FCM listener started for denbompa*

*2026-04-16 21:56:59 \[INFO] ServerManager: \[FCM] Starting listener for denbompa (attempt 2)*

*2026-04-16 21:56:59 \[WARNING] ServerManager: \[FCM] Listener startup key error for denbompa (attempt 2): 'fcm\_credentials'*

*2026-04-16 21:56:59 \[INFO] RustBot: Bot ready!*

*2026-04-16 21:56:59 \[INFO] RustBot: Raid alarm monitoring started*

*2026-04-16 21:57:01 \[INFO] ServerManager: \[FCM] Starting listener for denbompa (attempt 3)*

*2026-04-16 21:57:01 \[WARNING] ServerManager: \[FCM] Listener startup key error for denbompa (attempt 3): 'fcm\_credentials'*

*2026-04-16 21:57:03 \[INFO] ServerManager: \[FCM] Starting listener for denbompa (attempt 4)*

*2026-04-16 21:57:03 \[WARNING] ServerManager: \[FCM] Listener startup key error for denbompa (attempt 4): 'fcm\_credentials'*

*2026-04-16 21:57:05 \[INFO] ServerManager: \[FCM] Starting listener for denbompa (attempt 5)*

*2026-04-16 21:57:05 \[WARNING] ServerManager: \[FCM] Listener startup key error for denbompa (attempt 5): 'fcm\_credentials'*

*2026-04-16 21:57:07 \[ERROR] ServerManager: \[FCM] Listener failed after 5 attempts for denbompa - pairing notifications will not work*

*2026-04-16 21:59:09 \[INFO] RustBot: \[denbompa] ! help*

*2026-04-16 22:01:50 \[INFO] RustBot: \[denbompa] ! register*







#### TO TEST:

##### RaidAlarm:

&nbsp;	- Send DM with the message "You're being raided"
	- make bot join voicechat saying the same message


##### Fixes:

&nbsp;	- !uptime needs to show server uptime

&nbsp;	- !events needs to be checked on (active time etc)

&nbsp;	- Location of teammate upon death? Currently the GridLetter and Number are wrong. FYI not every map is the same size, therefore if a map is bigger there will be a column AA next to column Z. Rows are the numbers.









test: 

\- !addSM (add a storage monitor)

\- !viewSM (view the storage)

\- !deleteSM (delete storageMonitor



\- The problem lies with getting the pairing details from in-game. I will quickly explain the pairing process.

New server -> Pair server by: ESC then at the top of the screen there is a red button "PAIRING"; click on it; then Pair; next, open APP and PAIR.

\*after some time you have crafted Smart Devices\*

Take a wiring tool and look at the device in question, click pair.

This will send a request to your app to pair. => This request we want to emulate to our discordbot. So both the app and the bot receive the details the gameserver sends.



