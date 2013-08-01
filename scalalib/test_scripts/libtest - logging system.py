import os
import scalalib

filename = os.path.join(os.environ['HOMEDRIVE'], os.environ['HOMEPATH'], 
            'Desktop', 'scalalog.txt')

if __name__ == '__ax_main__':

    svars = scalalib.sharedvars()

    log = scalalib.get_logger( level='debug',
        scala=1, #ntevt=1, 
        # net=localhost:5292,   # use with net_listen
        svar='grab_debug',
        file=filename)
    
else:
    class obj: pass
    svars = obj()
    svars.log_text = 'watch out!!'
    grab_debug = obj()
    grab_debug.Value = 'dude'
    
    log = scalalib.get_logger( level='debug',
        con=1, 
        file=filename + '_cmd.txt' )

log.debug('low level stuff we dont normally want to see.')
log.info('informative stuff....')
log.warn(svars.log_text)
log.error('dagnabbit.')
log.critical('WE\'RE GONNA DIE!!!1!')

# print 'Grab debug =', grab_debug.Value 


