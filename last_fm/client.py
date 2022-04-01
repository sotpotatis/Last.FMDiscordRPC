'''client.py
Simple Last.FM client that is retrieving the things that I need.
'''
import logging, requests, time, datetime, pytz

#Set up logging
import math

logger = logging.getLogger(__name__)

class LastFMClient:
    def __init__(self, api_key: str):
        '''Defines a Last.FM client.

        :param api_key: The Last.FM API key.'''
        self.api_key = api_key

    def request(self, request_method: str, lastfm_method: str, params: dict):
        '''Defines and sends a request to Last.FM.

        :param request_method: The method to use for the request (GET, POST, etc.)

        :param lastfm_method: The Last.FM method to call for, for example user.getRecentTracks.
        :param params: The parameters to use in the request.'''

        #Add API key, method, and format to parameters
        params["api_key"] = self.api_key
        params["method"] = lastfm_method
        params["format"] = "json"


        #Send request
        request = requests.request(request_method, "https://ws.audioscrobbler.com/2.0/",
                                   params=params)
        if request.status_code not in [200, 204]:
            raise Exception(f"Request to Last.FM failed! (unexpected status code, text: {request.text})")
        else:
            return request.json() #Return request data

    def get_scrobbles(self, username: str, extended_results=True):
        '''Retrieves the scrobbles of a username and returns them in JSON format.

        :param username: The Last.FM username to get scrobbles for.

        :param extended_results: Whether to return extended results or not'''
        logger.debug(f"Getting scrobbles for {username}...")
        request = self.request("GET",  "user.getRecentTracks", {"user": username, "extended": extended_results})
        logger.debug("Scrobbles retrieved.")
        return request

    def get_track(self, track_mbid=None, artist=None, track_name=None):
        '''Function to get a track. NOTE: For the request to be successful, (MBID) or (artist and track name)
         must be set.

        :param track_mbid: The MBID of the track

        :param artist: The track artist

        :param track_name: The track name.
        '''
        body = {}
        if track_mbid != None:
            body["mbid"] = track_mbid
        if artist != None:
            body["artist"] = artist
        if track_name != None:
            body["track"] = track_name
        logger.debug(f"Getting track info for metadata {body}...")
        request = self.request("GET", "track.getInfo", body)
        logger.debug("Track info retrieved.")
        return request

    def get_currently_playing(self, username: str, include_recently_scrobbled=False, recent_scrobble_threshold_seconds=30, include_last_scrobble=False, last_scrobble_threshold_minutes=60):
        '''Retrieves a track that the user is currently playing or has recently scrobbled.

        :param username: Username to get now playing status for.

        :param include_recently_scrobbled: Use magic to tell whether a track has been scrobbled recently and include it if so in the listening status.
        This is really helpful for music services that doesn't scrobble a now playing track as now playing (such as Deezer)

        :param recent_scrobble_threshold_seconds: The time + track duration that is added to a scrobble start time to mark it as scrobbling if the include_recent_scrobbles is enabled.

        :param include_last_scrobble: Different from include_recent_scrobbles in the way that if this is enabled, it shows the recently listened track within the configured timeframe despite if they are currently playing or not, while include_recent_scrobbles tries to guess if a track is playing and only displays playing tracks.

        :param last_scrobble_threshold_minutes: If include_last_scrobble is True, tracks as old as [this value] minutes are included.
        '''
        logger.debug(f"Getting currently playing status for {username}...")
        #Get scrobbles
        scrobbles = self.get_scrobbles(username, extended_results=True)["recenttracks"]["track"]
        logger.debug("Scrobbles retrieved. Parsing...")
        #Get the latest scrobble
        latest_scrobble = scrobbles[0]
        #Query track info
        #Check if currently playing
        if "@attr" in latest_scrobble and "nowplaying" in latest_scrobble["@attr"] and latest_scrobble["@attr"]["nowplaying"]:
            logger.debug("Found currently playing track!")
            latest_scrobble["currently_playing"] = True
            return latest_scrobble #Return the scrobble as the currently playing track.
        elif include_recently_scrobbled:
            logger.debug("Didn't find a currently playing track, but magic has been enabled.")
            #Check the timestamp of the latest scrobble
            current_time = datetime.datetime.now(tz=pytz.UTC)
            timestamp_to_check_for = current_time.timestamp() #After this, the scrobble is not marked as recent
            #Check if the track has a duration
            #Query by MBID or artist and track name
            #...or nevermind, it doesn't work reliably somehow
            #if "mbid" in latest_scrobble and latest_scrobble["mbid"] != "":
             #   track_info = self.get_track(track_mbid=latest_scrobble["mbid"])
            #else:
            time.sleep(1) #Sleep until getting the next track
            track_info = self.get_track(track_name=latest_scrobble["name"], artist=latest_scrobble["artist"]["name"])
            track_played_unix_timestamp = int(latest_scrobble["date"]["uts"])
            track_duration = int(track_info["track"]["duration"])/1000 #(The value is in milliseconds, so divide by 1000 to get value in seconds)
            track_played_at_datetime = datetime.datetime.fromtimestamp(track_played_unix_timestamp).astimezone(tz=pytz.UTC)
            track_played_at = track_played_at_datetime.timestamp()
            track_timestamp_with_offsets_added = track_played_at + track_duration + recent_scrobble_threshold_seconds
            if track_timestamp_with_offsets_added > timestamp_to_check_for:
                logger.debug("Magic found a (possibly) current playing track!")
                latest_scrobble["currently_playing"] = None #Set currently playing status to unknown
                return latest_scrobble
            elif include_last_scrobble and (track_played_at_datetime + datetime.timedelta(minutes=last_scrobble_threshold_minutes)) > current_time:
                logger.debug("The last scrobble should be included and we are within the given threshold for last scrobbles. Returning latest scrobble...")
                latest_scrobble["currently_playing"] = False #Set currently playing status to not playing
                #Generate played_ago parameters
                playing_difference = (current_time - (track_played_at_datetime + datetime.timedelta(seconds=track_duration)))
                minutes_since_last_played = round(playing_difference.seconds / 60)
                played_ago = "unknown minutes"
                if minutes_since_last_played < 1:
                    played_ago = f"{playing_difference.seconds} s"
                elif minutes_since_last_played < 60:
                    played_ago = f"{minutes_since_last_played} m"
                else:
                    played_ago = f"{math.floor(minutes_since_last_played/60)} h"
                #Set played_ago parameter
                latest_scrobble["played_ago"] = played_ago
                return latest_scrobble, track_info

        #If we get here, we did not find a currently playing track
        logger.debug("Didn't find a currently playing track. Returning None...")
        return None

