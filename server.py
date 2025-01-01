import socket, threading
import asymmetric_encryption as ae

# Some server constants
HOST = "0.0.0.0"
PORT = 5556
USERNAME_MAX_LENGTH = 20
USERNAME_ALLOW_SPACES = False
SERVER_VERSION = 0.0

# Server variables
clients = []    # These variables are synced
keys = []       # This means users[1] corresponds to keys[1]
users = []
groups = []     # This one is complicated, it is a list of lists, every group is stored as a
                # seperate list, and indexed as groups[i][j], where i is the index of the group
                # and j is the index of the client
groupNames = [] # This list simply contains the names of all the groups, in order
                # meaning groupNames[1] is the name of group[1]


# Send a message to all clients except the sender
def send_message(message, sender=None):
    for group in groups:
        if sender in group:
            for i in group:
                if i == sender: continue

                clientId = clients.index(i)
                clientKey = keys[clientId]

                msg = ae.encrypt_message(message, clientKey)
                i.send(msg)
            return 0

    for i in range(len(clients)):
        msg = ae.encrypt_message(message, keys[i])
        clients[i].send(msg)


# Handle the clients
# This function is run for every connected client
def handle_client(client, publicKey, privateKey, clientKey):

    # Tell the client to continue
    message = ae.encrypt_message("OK", clientKey)
    client.send(message)

    # Start the handshake
    Recieving = False

    try:
        while not Recieving:
            # Setup the connection as per the clients requests
            message = client.recv(4096)
            time, message = ae.decrypt_message(message, privateKey)

            if message == "START_CONNECTION":
                # Start recieving messages from client
                Recieving = True
                send_message(f"{username} Joined the chat")

            elif message == "START_NAME_TRANSFER":
                # encrypt the username info to send
                info = ae.encrypt_message(USERNAME_MAX_LENGTH, clientKey)
                client.send(info)

                usernameAccepted = False
                while not usernameAccepted:
                    # recieve the username from the user
                    username = client.recv(4096)
                    time, username = ae.decrypt_message(username, privateKey)

                    status = ae.encrypt_message("VALID", clientKey)
                    usernameAccepted = True

                    #check if the username is valid
                    if len(username) > USERNAME_MAX_LENGTH:
                        status = ae.encrypt_message("INVALID", clientKey)
                        usernameAccepted = False

                    if " " in username and not USERNAME_ALLOW_SPACES:
                        status = ae.encrypt_message("INVALID", clientKey)
                        usernameAccepted = False

                    if username in users:
                        status = ae.encrypt_message("USERNAME TAKEN", clientKey)
                        usernameAccepted = False

                    client.send(status)

                # append the accepted name into the list
                users.append(username)

            elif message == "START_GROUP_SELECT":
                print("starting group selection")
                info = ae.encrypt_message(groupNames, clientKey)
                client.send(info)
                print("sent info")

                action = client.recv(4096)
                time, action = ae.decrypt_message(action, privateKey)

                status = ae.encrypt_message("OK", clientKey)
                client.send(status)

                if action == "join":
                    group = client.recv(4096)
                    time, group = ae.decrypt_message(group, privateKey)

                    status = ae.encrypt_message("OK", clientKey)

                    if group not in groupNames:
                        status = ae.encrypt_message("BAD", clientKey)

                    client.send(status)

                    groupId = groupNames.index(group)
                    groups[groupId].append(client)
                    print(groupId, groups, groupNames)

                elif action == "create":
                    group = client.recv(4096)
                    time, group = ae.decrypt_message(group, privateKey)

                    status = ae.encrypt_message("OK", clientKey)

                    if group in groupNames:
                        status = ae.encrypt_message("BAD", clientKey)

                    client.send(status)

                    groupId = len(groups)
                    groups.append([])
                    groups[groupId].append(client)
                    groupNames.append(group)

                    print(groupId, groups, groupNames)

        # Recieve messages from the client
        while 1:
            message = client.recv(4096)

            # If the message is completely empty, (this occurs when someone
            # Leaves), remove the user from all lists, and break the
            # connection to prevent ERROR 32: broken pipe
            if message == b'':
                remove_client(client, username)
                return

            time, message = ae.decrypt_message(message, privateKey)

            print(time, username,  message)
            send_message(f"{username}: {message}", client)

    except Exception as error:
        print(f"Error: {error}")
        remove_client(client, username)


# Removes a client
def remove_client(client, username):
    clientId = clients.index(client)
    clients.pop(clientId)
    keys.pop(clientId)
    users.remove(username)

    for i in groups:
        if client in i:
            groupId = groups.index(i)
            break

    clientId = groups[groupId].index(client)
    groups[groupId].pop(clientId)

    if groups[groupId] == []:
        groups.pop(groupId)
        groupNames.pop(groupId)

    client.close()

    send_message(f"{username} Left the chat")
    print(groups, groupNames)


# Guess what this does
def run_server():
    print("starting server...")

    # Initialise the keys
    print("creating keypair...")
    privateKey, publicKey = ae.generate_keys(4096)

    print("setting up socket...")
    # Initialise the server
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind((HOST, PORT))
    serverSocket.listen()

    print("succes!")

    print(f"started server on {HOST}:{PORT}")

    while 1:
        # Recieve clients
        client, address = serverSocket.accept()

        # Register the user
        clients.append(client)

        # Send public key to the client
        client.send(publicKey.encode())

        # Recieve clients public key and decrypt it
        clientKey = client.recv(4096)
        time, clientKey = ae.decrypt_message(clientKey, privateKey)

        # Add the key to the list of keys
        keys.append(clientKey)

        # Start a worker thread that will handle this client
        threading.Thread(target=handle_client, args=(client, publicKey, privateKey, clientKey)).start()



if __name__ == "__main__":
    run_server()
