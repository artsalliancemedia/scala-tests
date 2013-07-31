import sys, os, time
sys.path.append('.'); sys.path.append('..')
from glob import glob

import scalalib as sl
sl.get_logger(level='debug')

# scripts = [ os.path.abspath(x) for x in glob('*.sca') ]
scripts = glob('*.sca')
print 'publishing: ', scripts
print

targeturl = 'http://administrator:scala@localhost:8080/ContentManager?SCALA_CUSTOMER'
pubhandle = sl.publish(scripts, targeturl, options='d', tologger=True)

while False:
    status = sl.publish_check(pubhandle)
    print status
    print
    
    statstr = ('Publishing script %(currentscriptnum)s/%(numberofscripts)s'
        + ' "%(currentscriptname)s" %(overallpercentdone)s%% done.')
    print statstr % status
    print
    
    if status['overallpercentdone'] == '100': break
    time.sleep(2)