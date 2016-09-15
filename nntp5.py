import getopt
import nntplib, string, time, os
import pickle
import sys
import ConfigParser
import datetime
import subprocess

def gather( s, group, fileprefix, lim, lastsaved ):
    try:
        resp, count, first, last, name = s.group( group )
    except:
        print "ERROR"
        return [0, lastsaved]
    print 'Group', name, 'has', count, 'articles, range', first, 'to', last
    print 'Last saved was', lastsaved, "Left", int(last)-int(lastsaved)
    num = count
    if num > lim:
        num = lim
    # recalculate first/last so we only get the data we want.
    # we can choose the tkae the bottom range, or latest range...
    downloaded = 0    
    first_num = lastsaved #int( first )
    if first_num < int(first):
        first_num = int(first) #can't have less than server
    #last_num  = int( last )
    last_num = first_num + num
    #first_num = last_num - num + 1
    last_downloaded = first_num
    print "Downloading:", first_num, last_num, "/", int(last_num) - int(first_num)
    range = ( "%i-%s" % ( first_num, last_num ) )
    resp, subs = s.xhdr( 'subject', range )
    if verbose:
        print resp, subs
    for id, sub in subs[-num:]:
        #print id, sub
        filename = ( "%s.%0.8i" % ( fileprefix, int(id) ) )
        if os.path.exists( filename ):
            #print "exists", filename
            last_downloaded = int(id)
            continue
        try:
            resp, id, message_id, text = s.article(id)
            if verbose:
                print resp, id, message_id
                print "Saving:", filename
            fh = open(filename, 'w')
            for line in text:
                fh.write( line+'\n' );
            fh.close()
            downloaded += 1
            last_downloaded = int(id)
        except:
            pass
            #print "error:", id
    print "Downloaded:", downloaded
    return [downloaded , last_downloaded ]

# ----
try:
    df = subprocess.Popen(["df", "."], stdout=subprocess.PIPE)
    output = df.communicate()[0]
    device, size, used, available, percent, mountpoint = output.split("\n")[1].split()
    #print device, size, used, available, percent, mountpoint
    used = int(percent[:-1])
    if used > 95:
        print "No space on disk."
        sys.exit(8)
except:
    print "Cannot check disk"
    
servers = {}
groups  = []
noload = False
max_override = 0;
config_file = "nntp5.ini"
verbose = False


def check_pid(pid):        
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

lockfile = "/tmp/nntp5lock"
if os.path.exists( lockfile ):
    with open(lockfile, 'r') as f:
        pid = f.read()
        try:
            os.kill(int(pid), 0)
        except OSError:
            #not running, ok
            pass
        else:
            # this PID is running (could be something else...)
            print "Already running?"
            sys.exit(8)

fh = open(lockfile, 'w')
fh.write(str(os.getpid())+"\n")
fh.close()

lastlog = "/tmp/nntp5last.txt"
if os.path.exists( lastlog ):
    os.unlink(lastlog)

try:
    opts, args = getopt.getopt(sys.argv[1:], "c:nm:v", ["noload"] )
except getopt.GetoptError, err:
    print str(err) 
    sys.exit(2)
for o, a in opts:
    if o in ("-n", "--noload"):
        noload = True
    elif o in ("-m", "--regexp"):
        max_override = int(a)
    elif o in ("-c", "--config"):
       config_file = a
    elif o in ("-v", "--tags"):
        verbose = True
    else:
        assert False, "unhandled option"

config  = ConfigParser.ConfigParser()
read    = config.read( [ config_file ] )

servers = config.items( 'servers' )
dflt    = config.items( 'default' )

servers_config = {}
groups_config = {}

for server, server_cfg in servers:
  print "New server:", server, "=", server_cfg
  cfg = config.items( server_cfg )
  #print cfg
  servers_config[server] = {}
  for kv in cfg:
      servers_config[server][kv[0]] = kv[1] #keyword:value
  #
  groups = config.get( server_cfg, 'groups' )
  servers_config[server]['_groups'] = [] #internal group list
  #print groups                          #np,rasf1
  group_list = groups.split(",")
  for group in group_list:
      group_cfg = config.items( group ) # [np]
      #print group_cfg                   # all settings in [np]
      groups_config[group] = {}
      for kv in group_cfg: #store this in server settings?
          groups_config[group][kv[0]] = kv[1] #keyword:value
      servers_config[server]['_groups'].append(group)

#print servers_config['xs4all']
#print groups_config['np']

saved = {}

for server in servers_config:
    #    "xs4all": ["news.xs4all.nl", "pberck", "my88sore"] }
    host     = servers_config[server]['host']
    username = servers_config[server]['username']
    password = servers_config[server]['password']
    s = nntplib.NNTP(host, user=username, password=password)
    print s
    for group in servers_config[server]['_groups']:
        print group
        # check dir
        filedir = groups_config[group]['dir']
        if not os.path.exists(filedir):
            os.makedirs(filedir)
        groupname  = groups_config[group]['group']
        prefix     = filedir+groups_config[group]['prefix']
        num        = int(groups_config[group]['num'])
        lastsaved  = int(groups_config[group]['last'])
        #             gather( s, group, fileprefix, lim, lastsaved ):
        (num, last) = gather( s, groupname, prefix, num, lastsaved )
        saved[ group ] = num
        print "Saved until", last
        config.set( group, 'last', last ) #write back
    try:
        s.quit()
    except:
        print "Error in s.quit()"
        

# Write config back
config.set( 'default', 'timestamp', datetime.datetime.now() )
with open(config_file, 'wb') as configfile:
    config.write(configfile)

with open(lastlog, 'wb') as fh:
    for info in saved:
        fh.write(str(info)+":")
        fh.write(str(saved[info])+"\n")

for info in saved:
  print info, saved[info]

os.unlink(lockfile)

