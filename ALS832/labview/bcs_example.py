import bcs_tcp
address = "131.243.81.17"
port = 55000

def example():
    (host_ip_addr, host_port, host_timeout) = (address,port,60)

    # open TCP connection to BCS server running on localhost
    bcs = bcs_tcp.connection(host_ip_addr, host_port, host_timeout)
    print( bcs.ver() )
    print( bcs.listcommands() )
    # Move the X motor to position 0
    print( bcs.movemotor('Sample Rotation',0) )
    # Wait for BCS to report back that the motor has finished moving
    while 'Move in progress' in bcs.getmotorstat('Sample Rotation'):
        print(bcs.getmotorstat('Sample Rotation'))

    # Check the motor's status
    bcs.getmotorstat('Sample Rotation')

    # Trigger an error by sending an undefined command
    #bcs.enoble_motor()

    print( bcs.getsubsystemstatus() )

if __name__ == '__main__':
    example()
