import scalalib
import math
import sys

try:
    i.value = 2
    b.value = True
    # iarray.value = [1,2]
    s.value = 'set from libtest - var assign.py'
except NameError:
    pass
    
svars = scalalib.sharedvars()

svars.f = math.pi
svars.iarray = [10, 20] #, 30, 40]
# test one element array
svars.sarray = ['one'] #, 'two', 'three']

