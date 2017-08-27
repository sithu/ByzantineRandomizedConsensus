from base.broadcast import Broadcast
import json, threading, socket, queue


class ByzantineReliableBroadcast(Broadcast):
    """
    Implements a Byzantine Fault Tolerant Reliable Broadcast protocol.
    """

    BUFFER_SIZE = 1024


    def __init__(self, total_nodes, faulty_nodes, host_port, peer_list):
        """
        Constructs an instance of the Byzantine Reliable Broadcast protocol class.

        :param total_nodes: The total number of nodes in the network. Has to satisfy: N > 3f
        :param faulty_nodes: The maximum number of nodes that may be faulty in the network.
        :param host_port: The port where the instance can be reached.
        :param peer_list: A list of addresses for the rest of the nodes in the network. List of: [(ip, port)}
        """

        # Make sure that N > 3f
        assert total_nodes > 3*faulty_nodes

        super().__init__(total_nodes, faulty_nodes)

        self.port = host_port
        self.peers = peer_list

        # Check if echo has been sent and collect echo messages
        self.echo_sent_list = dict()

        # Check if ready has been sent and collect ready messages
        self.ready_sent_list = dict()

        # Keep delivered messages
        self.delivered_msgs = list()

    def broadcast(self, type, message):
        """
        Sends a message to all of the nodes in the network.

        :param message: The message to be sent.
        :return:
        """

        def _broadcast(final_msg):

            final_msg = final_msg.encode('utf-8')

            for addr in self.peers:
                broadcast_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                broadcast_client.connect(addr)
                broadcast_client.sendall(final_msg)
                broadcast_client.shutdown(socket.SHUT_RD)
                broadcast_client.close()

        message = {"source": socket.gethostname(), "type": type, "message": message}
        message = json.dumps(message)

        _broadcast(message)



    def _broadcast_listener(self):
        """
        A TCP socket server for listening to incomming messages

        :return:
        """

        server_listening = True

        host = socket.gethostname()
        broadcast_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        broadcast_server.bind(host, self.port)
        broadcast_server.listen(3 * self.N)

        # do accepts in separate thread
        while server_listening:
            client, address = broadcast_server.accept()
            message = client.recv(ByzantineReliableBroadcast.BUFFER_SIZE)
            if not message:
                print("Message was empty")
            dict_msg = json.loads(message)

            # for local testing
            peer_address = address[0] + ":" + address[1]
            # for general use
            # peer_address = address[0]

            # if msg not already delivered
            if dict_msg["message"] not in self.delivered_msgs:

                if dict_msg["type"] == Broadcast.MessageType.SEND and not self.echo_sent_list.has_key(dict_msg["message"]):

                    # insert message in dictionary (set ECHO flag to sent)
                    self.echo_sent_list[dict_msg["message"]] = set()

                    # broadcast ECHO msg
                    self.broadcast(Broadcast.MessageType.ECHO, dict_msg["message"])

                elif dict_msg["type"] == Broadcast.MessageType.ECHO:

                    # in case a SEND msg was not received, but ECHO received
                    if not self.echo_sent_list.has_key(dict_msg["message"]):
                        self.echo_sent_list[dict_msg["message"]] = set()
                        self.echo_sent_list[dict_msg["message"]].add(peer_address)

                    else:
                        self.echo_sent_list[dict_msg["message"]].add(peer_address)

                        # if more than (N+f)/2 ECHO msgs received, send READY msg
                        if len(self.echo_sent_list[dict_msg["message"]]) > (self.N + self.f) / 2 and not self.ready_sent_list.has_key(dict_msg["message"]):
                            self.ready_sent_list[dict_msg["message"]] = set()
                            # broadcast ready msg
                            self.broadcast(Broadcast.MessageType.READY, dict_msg["message"])

                elif dict_msg["type"] == Broadcast.MessageType.READY:

                    # in case a SEND and ECHO msgs were not received, but READY received
                    if not self.ready_sent_list.has_key(dict_msg["message"]):
                        self.ready_sent_list[dict_msg["message"]] = set()
                        self.ready_sent_list[dict_msg["message"]].add(peer_address)

                    else:
                        self.ready_sent_list[dict_msg["message"]].add(peer_address)

                        # if 2f READY msgs received, deliver msg
                        if len(self.ready_sent_list[dict_msg["message"]]) > 2*self.f:
                            self.deliver(dict_msg["message"])

                        # in case a SEND and ECHO msgs were not received, but f READY msgs received, send READY msg
                        elif not self.echo_sent_list.has_key(dict_msg["message"]) and len(self.ready_sent_list[dict_msg["message"]]) > self.f:
                            self.broadcast(Broadcast.MessageType.READY, dict_msg["message"])



    def broadcast_listener(self):
        """
        Listens for arriving messages from other nodes in the network.
        Runs on a separate thread.

        :return:
        """
        threading.Thread(target=self._broadcast_listener).start()

    def deliver(self, message):
        """
        Delivers a message sent from another node in the network

        :param sender: The sender's ID
        :param message: The message to be delivered.
        :return:
        """

        self.delivered_msgs.append(message)