import webservices.scws as scws
import json
import os


class ScalaMonitor:
    def __init__(self, baseurl, authstr, api):
        self.content_manager = scws.ConManager(baseurl, authstr, api_vers=api)

    def get_players(self):
        return dict((player.name, player.id)
                    for player in self.content_manager.PlayerRS.list())

    def set_player(self, player_id):
        """ Sets the player to be monitored by ScalaMonitor.

        Searches through all players, will find the first player that matches the provided name.
        """
        players = self.content_manager.PlayerRS.list()
        try:
            self.player =  next(p for p in players if p.id == player_id)
        except StopIteration as e:
            #re-raise as a more relevant exception
            self.player = None
            raise AttributeError(u'player ' + player_id + u' not found')

        print u'Player set to ' + self.player.name


    def get_player_info(self):
        """Returns

        {'frame_info : <see get_frame_info()>,
        'playlists' : [<see get_playlists()>],
        'media_on_disk':
        'name' : 'scala_box'
        }
        """
        output = {u'name' : self.player.name, u'id' : self.player.id}

        displays = self.content_manager.PlayerRS.getPlayerDisplays(playerId=self.player.id)

        if not displays: raise ValueError(u'No displays found for player ' + self.player.name)

        #should only ever be one - but better safe than sorry
        for display in displays:
            channels = self.content_manager.ChannelRS.get(channelId=display.channelId)
            if not channels: raise ValueError(u'No channels found for display ' + display.name)

            for channel in channels:
                output[u'frame_info'] = self.get_frame_info(channel)
                playlists = {}
                for frame in self.content_manager.ChannelRS.getFrames(channelId=channel.id):
                    print '------'
                    pls = self.get_playlists(channel.id, frame.id)
                    print pls
                    if(pls):
                        playlists[frame.name] = pls

                print 'w'*10
                output[u'playlists'] = playlists

        return output

    def get_frame_info(self, channel):
        """Returns frame info for a channel. Returns a dictionary that looks like the following:
        {'frames': [
            { 'name' : 'screen 1', 'dimensions' : '1920x1080'}
            ...
            ],
        'id':'1',
        'name':'My Frameset'
        }
        """
        framesets = self.content_manager.ChannelRS.getFrameset(channelId=channel.id)

        if not framesets: raise ValueError('No frameset found for channel ' + channel.name)

        frameset = {u'id' : framesets[0].id, u'name' : framesets[0].name}
        frames = self.content_manager.ChannelRS.getFrames(channelId=channel.id)

        frame_info = [ {u'name' : frame.name, u'dimensions' : frame.width + u'x' + frame.height}
                     for frame in frames if frame.audioTrack != 'true']

        frameset['frames'] = frame_info
        return frameset

    def get_playlists(self, channelId, frameId):
        #don't ask why channelId needs to be contained within a map - It just does
        timeslots = self.content_manager.ChannelRS.getTimeslots({u'channelId':channelId},frameId=frameId)
        for t in timeslots:
            if t.playlistId != None:
                pass

        return [timeslot.playlistId for timeslot in timeslots  if timeslot.playlistId != None]

def main():
    #read config file
    try:
        config = json.load(open(os.path.join(os.path.dirname(__file__), u'settings.json'), u'r'))
    except IOError:
        raise IOError(u'The settings.json file does not exist')

    scala = ScalaMonitor(config[u"baseurl"], config[u"authstring"], config[u"api"])
    players = scala.get_players()
    scala.set_player(players[u'Ski Kino 01'])

    print scala.get_player_info()

if __name__ == '__main__':
    main();
