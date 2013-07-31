import scalalib
import scalatools as st

svars = scalalib.sharedvars()

if __name__ == '__ax_main__':   # from scala

    log = scalalib.get_logger(  level='debug', svar='grab_debug',
        file='C:/Documents and Settings/mgmiller/Desktop/mikelog.txt')
        
    st.grab_url(svars.url, filename=svars.filename, minutes=2)
    
    # # authenticated tests
    # url = 'http://%s:%s/ContentManager/data/webdav/%s/redirect.xml'  % (
        # svars.cm_host, svars.cm_port, cm_network)
    # st.grab_url(url, filename='player_list.xml', 
        # username=svars.cm_user, password=svars.cm_pass)
        
else:                           # from command line
    log = scalalib.get_logger( con=1, level='debug' )
    
    st.grab_url('http://rss.news.yahoo.com/rss/science', 
        filename='science_rss.xml', minutes=1)

    # # authenticated tests
    st.grab_url('ftp://ftp.ubuntu.com/ubuntu/dists/intrepid-backports/Release', 
        filename='release2.txt', username='anonymous', password='dude.com')
        