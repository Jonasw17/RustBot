#### TODO:

- camera pictures? (https://github.com/liamcottle/rustplus.js/blob/master/camera.js)

- map jpeg for connection info (https://github.com/liamcottle/rustplus.js/blob/master/examples/5\_download\_map\_jpeg.js)

- Maybe AI integration





#### TO FIX: 

- commands working in-game chat, currently only works in discord 
- need a command to add a new raidalarm (smartalarm) to the database, and then have the bot check for it every 5 minutes or so, if there is a new one


#### TO TEST:

##### RaidAlarm:

- Send DM with the message "You're being raided"
	- make bot join voicechat saying the same message


##### Fixes:

	- !uptime needs to show server uptime

	- !events needs to be checked on (active time etc)

	- Location of teammate upon death? Currently the GridLetter and Number are wrong. FYI not every map is the same size, therefore if a map is bigger there will be a column AA next to column Z. Rows are the numbers.



test: 

- !addSM (add a storage monitor)

- !viewSM (view the storage)

- !deleteSM (delete storageMonitor



- The problem lies with getting the pairing details from in-game. I will quickly explain the pairing process.

New server -> Pair server by: ESC then at the top of the screen there is a red button "PAIRING"; click on it; then Pair; next, open APP and PAIR.

\*after some time you have crafted Smart Devices\*

Take a wiring tool and look at the device in question, click pair.

This will send a request to your app to pair. => This request we want to emulate to our discordbot. So both the app and the bot receive the details the gameserver sends.



