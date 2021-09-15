#import platform #os    # For getting the operating system name
#import subprocess  # For executing a shell command
import os, time
##
##hostname = '192.168.4.160' #example
##
##
####def ping(host):
####    """
####    Returns True if host (str) responds to a ping request.
####    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
####    """
####
####    # Option for the number of packets as a function of
####    #param = '-n' if platform.system().lower()=='windows' else '-c'
####    param = '-c'
####    
####    # Building the command. Ex: "ping -c 1 google.com"
####    command = ['ping', param, '1', host]
####
####    return subprocess.call(command) == 0
####    #return os.system.call(command) == 0
####
##
##   
##
####  response = os.system("ping -c 1 -t 3" + hostname)
##
####  and then check the response...
####  print( response == 0)
##
##
##def ping(hostname):
##    """
##    Returns True if host (str) responds to a ping request.
##    Remember that a host may not respond to a ping (ICMP) request
##    even if the host name is valid.
##    """
##    
##    command = 'ping -c 1 -t 3 '
##    response = os.system(command + hostname)
##
##    #and then check the response...
##    return ( response )
##
##tstart = time.time()
##
##for t in range (100000):
##   x = [1,3,5,7,9]
##   sum_squared = 0
##   for i in range(len(x)):
##       sum_squared+=x[i]**2
##       
##
##print(sum_squared)
##print('It took: %2.2f seconds' % (time.time()-tstart ))
##
##print('*'*8)
##
##tstart = time.time()
##
##for t in range (100000):
##   x = [1,3,5,7,9]
##   sum_squared = sum([ t*t for t in x])
##
##   
##
##print(sum_squared)
##print('Second run took: %2.2f seconds' % (time.time()-tstart ))
##
##
##
##

##a = []
##row = ['99']*3
##
##a = [row]*8
##
##a[1][2] = '55'
##
##print (a, a[1][2])
##for row in a:
##    for c in row:
##        print('c:', c, 'row:', row)
##

##a = [list(range(10)) for _ in range(10)]
##b = [0 for _ in range (10)]
##print(b)
##a = [ [0 for _ in range(10)] for _ in range(10)]
##a[1][2] = '55'
##
###print(list(range(10)))
##print (a, a[1][2])
##


# fill position 0 of 2D array
row         = [0]*8
col         = 3

open_krios  = [row]*col
closed_krios= [row]*col
cryo_krios  = [row]*col
mag_krios   = [row]*col
exps_krios  = [row]*col

print(open_krios,'\n', closed_krios)

row         = [1]*8

req = 2
open_krios[req][3]   = 1

print(open_krios, '\n', closed_krios)


##
##closed_krios[req] = (closedsec)
##cryo_krios[req]   = (cryo)
##mag_krios[req]    = (mag)
##exps_krios[req]   = (exps)
##month_krios[req]  = (month)




