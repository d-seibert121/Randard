# Randard

Randard was born of a simple question, asked by me to my Magic playing friends in college: "What if, instead of playing Standard, we made our own format? We could just pick a handful of totally random sets, and see what we can build!"

What is Randard?
Randard is a rotating format, but one unlike any in Magic's official formats. Instead of only 1 or two sets rotating in and out at a given time, Randard changes wholesale every 3 months. This constantly gives players an entirely new collection of roughly 2,000 cards to make decks from, posing interesting deckbuilding challenges that are entirely new every rotation. Players are encouraged to use free online MTG clients like untap.in, Cocatrice, or Xmage to play, or use proxies if playing in person, since the format is more about the deeckbuilding challenge than being a truely competitive experience.

What is this repository?
This repository contains two Python packages. One, simply called Randard, is a utility: it interfaces with the mtgsdk package and an sqlite3 database to fetch, store, and manage information about Magic cards and sets. In particular, it contains functions for parsing decklist files, checking those decklists against custom formats for legality, and storing season info (including what sets are legal, for example) for a Randard league. The other, RandardDiscordBot, is just that: a Discord Bot. It takes care of the work of managing a Randard league. Players can register for the league, record games, track their rating (using an ELO variant by default), double check what sets the current format contains, and more, all through the intuitive interface of Discord's Slash Commands.

How do I use this bot?
Eventually, I plan to host the bot somewhere, so it will be as simple as inviting the bot to your server. In the meantime, I've tried to make it as simple to deploy your own copy as possible if you are on Windows. First, you'll need to make a bot via Discords dev portal. The bot will need the "Manage Roles", "Manage Channels", "Read Messages/View Channels", "Send Messages", "Send Messages in Threads", "Embed Links", and just to be safe, the "Use Slash Commands" permissions. Invite the bot to your server with those permissions, it's under OAuth2 -> URL Generator. 
Next, within the main directory of the repo (the outer Randard folder), create a private_info.py file with 3 lines: 
TOKEN='your_bots_token'
TEST_GUILDS=[your_servers_id]
DB_LOC='some_unused_filepath.db'
Note the brackets and quotes. The token is unique to your copy of the bot, and can be found via the Discord Dev portal. You can find your server's id from the Discord client: go to your server settings, under the "Widget" heading, it's listed as "SERVER ID". And the DB_LOC could be litterally anywhere, but I'd put it in the main directory of the repo. You don't have to actually create a database, just give it a valid filepath and the bot will do that for you.
Once you do all that, just launch the BotLauncher.bat and the bot should appear online in your server. All of the interaction with the bot is launched via slash commands, so just type a / in your server and the commands should pop up! As you type in a name, it'll also prompt you for what arguments that command needs, if any.
