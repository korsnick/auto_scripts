#!/usr/bin/python

###############################################################################
# name: autoinject.py
# auth: korsnick
# date: 12/2010

import sys
import pexpect
import csv
import time
import datetime
#import pdb
 
from atf_funcs import *
 
###############################################################################
# FUNCTIONS
def phyp_cmd(px, command):
    
    """ Does the main work of getting a prompt and sending the commands.
    Takes a pexpect object and a command string to send."""
    
    print '  -%s' %command
    if after_inject:
        log_comment(px, 'POST-INJECT / %s' %command)
    else:
        log_comment(px, 'PRE-INJECT / %s' %command)
    px.sendline(command)
     
    # getting this prompt can be flaky for some reason so loop unit we get it
    px.expect('phyp # ')
    while px.before.strip() == 'Could not parse a macro name':
        phyp.sendline(command)
        phyp.expect('phyp # ')


def get_srcs(px):
    px.sendline('errl -l ')
    
###############################################################################
   
#pdb.set_trace()

# read in machine specific settings from the config file
print '\n* Reading config file'
cfg = parse_config(sys.argv[1])
#cfg = parse_config('/home/ppk/ibm/falcon/bfsp067/bfsp067.cfg')
#cfg = parse_config('/home/ppk/IBM/jupiter/jioc09a/jioc09a.cfg')j
#cfg = parse_config('/home/ppk/ibm/falcon/pfd3nb24/pfd3nb24.cfg')

# check LID version
print '* Checking LID version'
lid = parse_config('lid.log')

# has the inject happened yet
after_inject = False

# show config settings to user
print '* Current Settings:'
print '  -machine: %s' %cfg['machine']
print '  -lid: %s' %lid['lid']
print '  -hub: %s' %cfg['hubnumber']
print '  -phb: %s' %cfg['phbnumber']

# connect to FSP
print '* Connecting to FSP %s...' %cfg['machine']
fsp = pexpect.spawn('telnet %s' %cfg['machine'], timeout=None)
fout_fsp = file('fsp.log', 'w')
fsp.logfile = fout_fsp
fsp.expect('login: ')
fsp.sendline('root')
fsp.expect('Password: ')
fsp.sendline('FipSroot')
fsp.expect(cfg['fsp_prompt'])

# set up PHYP tunnel
print '* Setting up tunnel'
vtty = pexpect.spawn('ssh -l %s %s vtty-fsp %s -timeout=0 -setuponly'
                     %(cfg['user'], cfg['host'], cfg['machine']), timeout=None)
vtty.expect ('password: ')
vtty.sendline(cfg['password'])
fout_vtty = file('.vtty.log', 'w')
vtty.logfile = fout_vtty
vtty.expect(pexpect.EOF)
vtty.close()

# setup CSV file parser to read in each test case from listing file
inputFile = open(sys.argv[2], 'rb')
parser = csv.reader(inputFile)

# loop through each testcase in the listing file
# opening the connection needs to be inside the loop in case the CEC is rebooted (ala GXE's)
for to_be_run, case_name, is_phb, offset, bits in parser:

    # remove any whitespace
    to_be_run = to_be_run.strip()

    if to_be_run == '1':
        
        # clean up the rest
        case_name = case_name.strip()
        is_phb = is_phb.strip()
        offset = offset.strip()
        bits = bits.strip()
        address = cfg['hub_base_addr'].strip()
        
        print '* Running test case: %s' %case_name
        
        # connect to tunnel
        # all this crap is required because it's impossible to get a phyp prompt reliably
        i = 1
        while i == 1:
            print '* Telnetting to PHYP'
            phyp = pexpect.spawn('telnet %s 30002' %cfg['machine'],
                                 timeout=None)
            i = phyp.expect(['phyp # ', '0x0'])
            if i == 1:
                phyp.close()
                time.sleep(1)
        
        # record the input and output from the phyp session
        fout_phyp = file('./traces/%s' %case_name, 'w')
        phyp.logfile = fout_phyp
        
        # setup address and offsets 
        if is_phb == 'yes': address = phb_offset(address, cfg['phbnumber'])
        address = (hex_add(address, offset)[2:]).zfill(16)
        
        # BEGIN
        phyp.logfile.write('/////////////////////////////////////////////////////////////////////////////////////////\n')
        phyp.logfile.write('/ TESTCASE: %s\n' %case_name)
        phyp.logfile.write('/ MACHINE: %s\n' %cfg['machine'])
        phyp.logfile.write('/ LID: %s\n' %lid['lid'])
        phyp.logfile.write('/ START: %s\n' %datetime.datetime.now())
        phyp.logfile.write('/////////////////////////////////////////////////////////////////////////////////////////\n')

        # start sending the commands to phyp
        print '* Sending commands'
        
        phyp_cmd(phyp, 'xmfr')
        phyp_cmd(phyp, 'xmdumptrace -hub %s -ctrl -detail 2' %cfg['hubnumber'])
        phyp_cmd(phyp, 'xmdumptrace -b %s -detail 2' %cfg['phb_hex'])
        phyp_cmd(phyp, 'xmdumpbuserrors %s' %cfg['bus_drc'])
        phyp_cmd(phyp, 'xmdumpp7iocregs -hub all -lem')
        phyp_cmd(phyp, 'xmquery -q allrio -d 2')
        phyp_cmd(phyp, 'xmquery -q allslots -d 2')
        phyp_cmd(phyp, 'xmquery -q allslots -d 1')
        #get_srcs()
        
        # INJECT
        phyp.logfile.write('\n')
        phyp.logfile.write('/////////////////////////////////////////////////////////////////////////////////////////\n')
        phyp.logfile.write('/////////////////////////////////////////////////////////////////////////////////////////\n')
        phyp_cmd(phyp,'xmwritememory %s %s' %(address, bits))
        time.sleep(30)
        after_inject = True
        phyp.logfile.write('\n')
        phyp.logfile.write('/////////////////////////////////////////////////////////////////////////////////////////\n')
        phyp.logfile.write('/////////////////////////////////////////////////////////////////////////////////////////\n')
        
        #get_srcs()
        phyp_cmd(phyp, 'xmdumptrace -hub %s -ctrl -detail 2' %cfg['hubnumber'])
        phyp_cmd(phyp, 'xmdumptrace -b %s -detail 2' %cfg['phb_hex'])
        phyp_cmd(phyp, 'xmdumpbuserrors %s' %cfg['bus_drc'])
        phyp_cmd(phyp, 'xmdumpp7iocregs -hub all -lem')
        phyp_cmd(phyp, 'xmquery -q allrio -d 2')
        phyp_cmd(phyp, 'xmquery -q allslots -d 2')
        phyp_cmd(phyp, 'xmquery -q allslots -d 1')
        phyp_cmd(phyp, 'xmfr')

        phyp.close()

        # see if user wants to continue
        q = raw_input('Run next case, y/n? ')
        if q == 'n': break
        
fsp.close()