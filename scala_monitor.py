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


    def get_stored_content(self):
        channel_filter = scws.TObj()
        channel_filter.id
        channels = self.content_manager.ChannelRS.list(searchCriteria=channel_filter)
        meta = self.content_manager.PlayerRS.getMetaValues(player.id)
        print meta


def main():
    #read config file
    try:
        config = json.load(open(os.path.join(os.path.dirname(__file__), u'settings.json'), u'r'))
    except IOError:
        raise IOError(u'The settings.json file does not exist')

    scala = ScalaMonitor(config[u"baseurl"], config[u"authstring"], config[u"api"])
    players = scala.get_players()
    print players
    scala.set_player(players[u'Ski Kino 01'])

    scala.get_stored_content()

if __name__ == '__main__':
    main();
