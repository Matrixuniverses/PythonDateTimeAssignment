"""
COSC264 Assignment
Author: sjs227
Due date: 21/08/2018

Client application that creates a DT-Request and sends it to the server, the language is determined
by what port the DT-Request packet is sent to. The client will then use select() to wait for timeout
if no packet is received. If a packet is received the values inside are checked before displaying the
content. Some basic error checking is done when the client is run and of the packet contents
"""


from select import select
import argparse
import socket
import sys

# Packet header constants
MAGIC_NUMBER = 0x497E
DT_REQ = 0x0001
DT_RES = 0x0002
REQ_DATE = 0x0001
REQ_TIME = 0x0002
TIMEOUT = 1.0


def check_arguments():
    """
    Checks the arguments supplied to the program upon execution using argparser. Also checks that the server
    address is resolvable and the port number is valid before returning the request type, address and port

    :return: Int for request type, dotted decimal host address and int of port number
    """

    # Defining the command line positional arguments and types
    parser = argparse.ArgumentParser()
    parser.add_argument('type', help="Type of request to send: date/time", type=str, choices=['date', 'time'])
    parser.add_argument('address', help="Host address of the server receiving DT_Requests", type=str)
    parser.add_argument('port', help="Port number on the application server receiving DT_Requests", type=int)
    args = parser.parse_args()

    # Attempts to resolve the given hostname or address, exiting if failed
    try:
        host_addr = socket.gethostbyname(args.address)
    except socket.error as e:
        print(e)
        print("Stopping..")
        sys.exit()
    
    # Checks the range of the port number, cannot be in the reserved system ports or too large
    if args.port < 1024 or args.port > 64000:
        print("Invalid port, must be in range 1024 - 64000\nStopping..\n")
        sys.exit()

    return args.type, host_addr, args.port


def packet_create(req_type):
    """
    Creates a DT-Request packet with the request type and magic number 
    
    :param req_type: Int representing the request type being date or time
    :return: Bytearray containing a DT-Request packet
    """

    packet = bytearray(6)
    packet[0:2] = MAGIC_NUMBER.to_bytes(2, "big")
    packet[2:4] = DT_REQ.to_bytes(2, "big")
    if req_type == 'date':
        packet[4:6] = REQ_DATE.to_bytes(2, "big")
    if req_type == 'time':
        packet[4:6] = REQ_TIME.to_bytes(2, "big")

    return packet


def socket_open(host_addr, port_num, transmit_packet):
    """ 
    Opens a UDP socket with the given address and port number, and waits until timeout for a response.
    If a response is received then the packet is returned to be checked

    :param host_addr: String containing dotted decimal host address
    :param port_num: Int of the host port to connect to
    :param transmit_packet: Bytearray containing the packet to transmit
    :return: Bytearray containing the received packet from host
    """
    
    # Attempts to open a socket with the given host address and port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except socket.error as e:
        print(e)
        print("Stopping..\n")
        sys.exit()

    # Sending DT_Request packet to opened socket
    sock.sendto(transmit_packet, (host_addr, port_num))
    
    # Using a blocking system call to wait for a packet response before timing out 
    readable, writable, exceptional = select([sock], [], [], TIMEOUT)
    
    # If socket has received a response before the timeout time then there will be no readable data
    if len(readable) == 0:
        err_str = "[ERROR] ** Timeout occurred: {0}:{1} failed to respond within {2}s"
        print(err_str.format(host_addr, port_num, TIMEOUT))
        sys.exit()

    # If there is readable data in the buffer then the socket data is received
    elif len(readable) > 0:
        socket_receiving = readable[0]
        received_packet = socket_receiving.recvfrom(1024)
        rec_str = "[INFO] -- Received packet from {0}:{1}\n[DATA] -- {2}\n"
        print(rec_str.format(received_packet[1][0], received_packet[1][1], received_packet[0]))
    
    # Close the socket as it is no longer needed
    sock.close()

    return received_packet


def process_packet(packet):
    """ 
    Takes the received packet and performs checks to ensure it is a valid DT-Response, and prints contents to
    stdout if packet is valid, error otherwise

    :param packet: Bytearray containing the packet received from the opened socket with server
    """
    
    # If the length of the packet is too small, exit before index out of range errors occur
    if len(packet) < 13:
        print("[ALERT] ** Malformed packet received")
        sys.exit()
    
    # Extracting information from fields
    rec_magic_num = int.from_bytes(packet[0:2], "big")
    rec_packet_type = int.from_bytes(packet[2:4], "big")
    rec_lang_code = int.from_bytes(packet[4:6], "big")
    rec_year = int.from_bytes(packet[6:8], "big")
    rec_month = packet[8]
    rec_day = packet[9]
    rec_hour = packet[10]
    rec_min = packet[11]
    rec_len = packet[12]

    # Conditionals to check validity of packet fields
    if rec_magic_num != MAGIC_NUMBER:
        print("[WARN] ** Non DT packet received")
        sys.exit()
    if rec_packet_type != DT_RES:
        print("[WARN] ** Non DT-Response packet received")
        sys.exit()
    if rec_lang_code not in [0x1, 0x2, 0x3]:
        print("[WARN] ** Invalid language code in received DT-Response")
        sys.exit()
    if rec_year >= 2100:
        print("[WARN] ** Invalid year number in received DT-Response")
        sys.exit()
    if rec_month < 1 or rec_month > 12:
        print("[WARN] ** Invalid month number in received DT-Response")
        sys.exit()
    if rec_day < 1 or rec_day > 31:
        print("[WARN] ** Invalid day number in received DT-Response")
        sys.exit()
    if rec_hour < 0 or rec_hour > 24:
        print("[WARN] ** Invalid hour number in received DT-Response")
        sys.exit()
    if rec_min < 0 or rec_min > 60:
        print("[WARN] ** Invalid minute number in received DT-Response")
        sys.exit()
    if (rec_len + 13) != len(packet):
        print("[WARN] ** Packet lengths do not match")
        sys.exit()
    
    # Nicely formatted output of a valid DT-Response
    type_str = "[DATA] -- Magic Number: {0}\t\tPacket type: {1}\t\tLanguage code: {2}"
    date_str = "[DATA] -- Date: {0:04d}-{1:02d}-{2:02d}\t\tTime: {3:02d}:{4:02d}"
    text_str = "[DATA] -- Text: {0}"

    print(type_str.format(hex(rec_magic_num), rec_packet_type, rec_lang_code))
    print(date_str.format(rec_day, rec_month, rec_year, rec_hour, rec_min))
    print(text_str.format(packet[13:].decode('UTF-8')))


def main():
    """
    Program setup, gets request type, host address and port number from check_arguments() then creates and
    sends a DT-Request. Upon receiving a packet, runs process_packet() to check validity and contents
    """

    req_type, host_addr, host_port = check_arguments()
    tx_packet = packet_create(req_type)
    return_packet = socket_open(host_addr, host_port, tx_packet)
    process_packet(return_packet[0])


if __name__ == "__main__":
    main()
