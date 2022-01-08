'''Last.FM Discord RPC
Shows the last scrobble or the currently playing song from your Last.FM
profile as a Discord Rich Presence.
'''

import logging, os, toml, time #Import required modules
from pypresence import Presence

#Set up logging
from last_fm.client import LastFMClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG) #Set global logging level to info.
#Get paths and load config file
logger.info("Reading app configuration...")
MAIN_SCRIPT_FILEPATH = os.path.realpath(__file__)
PROJECT_DIRECTORY = os.path.dirname(MAIN_SCRIPT_FILEPATH)
CONFIG_FILEPATH = os.path.join(PROJECT_DIRECTORY, "config.toml")
try: #Attempt to read the configuration file
    config = toml.loads(open(CONFIG_FILEPATH, "r").read())
except Exception as e:
    logger.critical("Failed to read configuration. Make sure that the file \"config.toml\" exists in the presence directory and that it is valid.", exc_info=True)
    exit()
#Read configiration parameters
logger.info("Reading configuration parameters. If you get an error here, check that you have set everything in your configuration.")
last_fm_config = config["last_fm"]
last_fm_api_key = last_fm_config["api_key"]
last_fm_profile_to_monitor = last_fm_config["profile_to_monitor"]
last_fm_poll_status_every_n_s = last_fm_config["poll_status_every_n_s"]
last_fm_include_recent_scrobbles = last_fm_config["include_recent_scrobbles"]
last_fm_recent_scrobble_threshold_seconds = last_fm_config["recent_scrobble_threshold_seconds"]
last_fm_include_last_scrobble = last_fm_config["include_last_scrobble"]
last_fm_last_scrobble_threshold_minutes = last_fm_config["last_scrobble_threshold_minutes"]
discord_config = config["discord"]
discord_client_id = discord_config["client_id"]
retry_failed_rpc_connections_after = discord_config["retry_failed_rpc_connections_after"]
differentiate_magic_scrobbles_status = discord_config["differentiate_magic_scrobbles_status"]
logger.info("Configuration parameters read. Looking good!")

rpc = Presence(discord_client_id)
lfm = LastFMClient(last_fm_api_key)
def reconnect_to_discord():
    '''Function to handle a failed connection to Discord or just reconnect until
    a connection becomes available.
    Attempts to reconnect itself until successful.'''
    logger.info("Trying to reconnect to Discord...")
    try:
        rpc.connect()
        logger.info("Connection succeeded!")
        return #Exit the function
    except Exception as e:
        logger.warning("Failed to connect to Discord. Make sure that the app is running and check your firewall.", exc_info=True)
        logger.info(f"Retrying connection in {retry_failed_rpc_connections_after} seconds...")
        time.sleep(retry_failed_rpc_connections_after)
        reconnect_to_discord() #Call the function again to reconnect

#Main loop.
logger.debug("Connecting to Discord before mainloop...")
reconnect_to_discord()

#Run mainloop
while True:
    try:
        logger.info("Polling for status from Last.FM...")
        currently_playing_track = lfm.get_currently_playing(last_fm_profile_to_monitor,
                                                            include_recently_scrobbled=last_fm_include_recent_scrobbles,
                                                            recent_scrobble_threshold_seconds=last_fm_recent_scrobble_threshold_seconds,
                                                            include_last_scrobble=last_fm_include_last_scrobble,
                                                            last_scrobble_threshold_minutes=last_fm_last_scrobble_threshold_minutes)
        if currently_playing_track == None:
            logger.info("Nothing isn't currently playing. Clearing status...")
            try:
                rpc.clear() #Clear the status
            except Exception as e:
                logger.warning("Something went wrong when trying to connect to Discord. Attempting to reconnect...", exc_info=True)
                reconnect_to_discord()
        else:
            logger.info("Something is currently playing!")
            #Parse playing status
            track_is_currently_playing = currently_playing_track["currently_playing"]
            if track_is_currently_playing:
                status = "Playing"
            elif track_is_currently_playing == None:
                if differentiate_magic_scrobbles_status:
                    status = "Playing / recently played"
                else:
                    status = "Playing"
            elif track_is_currently_playing == False:
                status = f"Played {currently_playing_track['played_ago']} ago" #The get_currently_playing function adds a unique parameter when the track was played
            track_name = currently_playing_track["name"]
            artist_name = currently_playing_track["artist"]["name"]
            album_name = currently_playing_track["album"]["#text"]
            track_image_url = currently_playing_track["image"][-1]["#text"] #This should return the biggest image
            if "loved" in currently_playing_track and currently_playing_track["loved"] == "1":
                track_loved = True
            else:
                track_loved = False
            #Parse small image
            if track_loved:
                small_image_key = "heart"
                small_image_text = "Favorite track"
            elif track_is_currently_playing == False:
                small_image_key = "last_played"
                small_image_text = "Played recently"
            else:
                small_image_key = "playing"
                small_image_text = "Playing"
            #Parse track playing time and add it if the track is currently played or was recently played
            start = None
            if "date" in currently_playing_track and "uts" in currently_playing_track["date"] and track_is_currently_playing != False:
                start = currently_playing_track["date"]["uts"]
            #Get links to track and album
            buttons = []
            if "url" in currently_playing_track:
                buttons.append({ #Add button for currently playing track
                    "label": "View track",
                    "url": currently_playing_track["url"]
                })
            if "url" in currently_playing_track["artist"]:
                buttons.append({ #Add button for currently playing artist
                    "label": "View artist",
                    "url": currently_playing_track["artist"]["url"]
                })
            try:
                rpc.update(
                    state=f"{track_name} - {artist_name}",
                    details=status,
                    large_image=track_image_url, #Set large image to current playing album.
                    large_text=f"On album \"{album_name}\"",
                    small_image=small_image_key,
                    small_text=small_image_text,
                    buttons=buttons,
                    start=start
                )
            except Exception as e:
                logger.warning("Something went wrong when trying to update status to Discord. Attempting to reconnect...", exc_info=True)
                reconnect_to_discord()
    except Exception as e:
        logger.critical("Something went wrong in the script main loop. An unhandled exception occurred.", exc_info=True)
        logger.info("Waiting 30 seconds until re-poll...")
        time.sleep(30) #Wait 30 seconds

    logger.info(f"Waiting {last_fm_poll_status_every_n_s} seconds until repoll...")
    time.sleep(last_fm_poll_status_every_n_s)
