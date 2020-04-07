import socket
import sys
from pathlib import Path

def main():
	host = '127.0.0.1'
	command_channel_port = int(sys.argv[1])
	data_channel_port = int(sys.argv[2])
	command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	command_socket.connect((host, command_channel_port))
	data_socket.connect((host, data_channel_port))
	file_name = ""

	while True:
		command = input()
		command_socket.send(command.encode("ascii"))
		result = command_socket.recv(2048).decode()
		print(result)

		if "DL" in command:
			file_name = Path(command[3 :]).name

		if "226 List transfer done" in result:
			size = int(data_socket.recv(16).decode())
			print(data_socket.recv(size).decode())
		elif "226 Successful Download" in result:
			size = int(data_socket.recv(16).decode())
			data = data_socket.recv(size).decode()
			new_file = open(file_name, "w")
			new_file.write(data)
			new_file.close()
		elif "221" in result:
			break

	command_socket.close()
	data_socket.close()

if __name__ == "__main__":
	main()