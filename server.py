import socket
import threading
import rapidjson
import io
import os
import shutil
from _thread import start_new_thread
from pathlib import Path
from datetime import datetime

log_lock = threading.Lock()
mail_lock = threading.Lock()

def logger(logging_enable, logging_path, message):
	if logging_enable:
		log_lock.acquire()
		log_file = open(logging_path, "a")
		log_file.write("At " + datetime.now().__str__() + ": " + message + "\n")
		log_file.close()
		log_lock.release()

def send_alert(name, threshold, mail):
	mail_lock.acquire()
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect(("mail.ut.ac.ir", 25))
	sock.recv(256)
	sock.send("HELO mrazimi99@ut.ac.ir\r\n".encode("ascii"))
	sock.recv(256)
	sock.send("MAIL from: <mrazimi99@ut.ac.ir>\r\n".encode("ascii"))
	sock.recv(256)
	sock.send("AUTH LOGIN\r\n".encode("ascii"))
	sock.recv(256)
	sock.send("bXJhemltaTk5\r\n".encode("ascii"))
	sock.recv(256)
	sock.send("MTAxNk1BMTAxNm1h\r\n".encode("ascii"))
	sock.recv(256)
	sock.send(("RCPT to: <" + mail + ">\r\n").encode("ascii"))
	sock.recv(256)
	sock.send("DATA\r\n".encode("ascii"))
	sock.recv(256)
	sock.send("Subject: FTP Service Alert\r\n".encode("ascii"))
	sock.send(("Hi dear " + name +".\r\nYour remained size is less than " + str(threshold) + ".\r\n.\r\n").encode("ascii"))
	sock.recv(256)
	sock.send("QUIT\r\n".encode("ascii"))
	sock.recv(256)
	sock.close()
	mail_lock.release()

def serve(command_client, data_client, config):
	users = config["users"]
	accounting = config["accounting"]
	accounting_enable = accounting["enable"]
	accounting_threshold = accounting["threshold"]
	accounting_users = accounting["users"]
	logging_enable = config["logging"]["enable"]
	logging_path = config["logging"]["path"]
	authorization = config["authorization"]
	authorization_enable = authorization["enable"]
	authorization_admins = authorization["admins"]
	authorization_files = authorization["files"]
	state = 0
	username = ""
	wd = Path(os.getcwd())
	home = wd

	while True:
		data = command_client.recv(1024)
		message = ""
		data_message = ""

		if not data:
			break

		command = data.decode()

		if command[: 5] == "USER ":
			if state == 0:
				arguments = command[5 :].split()

				if len(arguments) != 1:
					message = "501 Syntax error in parameters or arguments."
				else:
					username = arguments[0]

					for pair in users:
						if pair["user"] == username:
							state = 1
							message = "331 User name okey, need password."
							break

					if state != 1:
						message = "430 Invalid username or password."
			else:
				message = "503 Bad sequence of commands."

		elif command[: 5] == "PASS ":
			if state == 1:
				arguments = command[5 :].split()

				if len(arguments) != 1:
					message = "501 Syntax error in parameters or arguments."
				else:
					password = arguments[0]

					for pair in users:
						if pair["user"] == username:
							if pair["password"] == password:
								state = 2
								logger(logging_enable, logging_path, "User " + username + " logged in.")
								message = "230 User logged in, proceed."
							else:
								state = 0
								message = "430 Invalid username or password."
							break
			else:
				message = "503 Bad sequence of commands."

		elif state == 2:
			if command == "PWD":
				message = "257 " + wd.__str__()

			elif command[: 4] == "MKD ":
				arguments = command[4 :].split()

				if len(arguments) == 1:
					wd.joinpath(arguments[0]).mkdir()
					logger(logging_enable, logging_path, "User " + username + " created a directory named " + arguments[0])
					message = "257 " + arguments[0] + " created."
				elif len(arguments) == 2 and arguments[0] == "-i":
					wd.joinpath(arguments[1]).touch()
					logger(logging_enable, logging_path, "User " + username + " created a file named " + arguments[1])
					message = "257 " + arguments[1] + " created."
				else:
					message = "501 Syntax error in parameters or arguments."

			elif command[: 4] == "RMD ":
				arguments = command[4 :].split()

				if len(arguments) == 1:
					if wd.joinpath(arguments[0]).is_file():
						if not (authorization_enable and username not in authorization_admins and wd.joinpath(arguments[0]) in [home.joinpath(f) for f in authorization_files]):
							os.remove(wd.joinpath(arguments[0]))
							logger(logging_enable, logging_path, "User " + username + " removed a file named " + arguments[0])
							message = "250 " + arguments[0] + " deleted."
						else:
							message = "550 File unavailable."
					else:
						message = "500 Error."
				elif len(arguments) == 2 and arguments[0] == "-f":
					if wd.joinpath(arguments[1]).is_dir():
						shutil.rmtree(wd.joinpath(arguments[1]))
						logger(logging_enable, logging_path, "User " + username + " removed a directory named " + arguments[1])
						message = "250 " + arguments[1] + " deleted."
					else:
						message = "500 Error."
				else:
					message = "501 Syntax error in parameters or arguments."

			elif command == "LIST":
				data_message = ""

				for elem in os.listdir(wd):
					data_message += elem + "\n"

				if len(data_message) > 0:
					data_message = data_message[: -1]
				else:
					data_message = "empty"

				size = str(len(data_message))
				size = "0" * (16 - len(size)) + size
				data_message = size + data_message
				data_message = data_message.encode("ascii")

				message = "226 List transfer done."

			elif command[: 3] == "CWD":
				arguments = command[4 :].split()

				if len(arguments) == 0:
					wd = home
				elif len(arguments) == 1 and arguments[0] == "..":
					wd = wd.parent
				elif len(arguments) == 1:
					wd = Path(wd.joinpath(command[4 :]))
				else:
					message = "501 Syntax error in parameters or arguments."

				message = "250 Successful Change."

			elif command[: 3] == "DL ":
				arguments = command[3 :].split()

				if len(arguments) != 1:
					message = "501 Syntax error in parameters or arguments."
				elif wd.joinpath(arguments[0]).is_file():
					if not (authorization_enable and username not in authorization_admins and wd.joinpath(arguments[0]) in [home.joinpath(f) for f in authorization_files]):
						data_message = wd.joinpath(arguments[0]).read_bytes()
						size = str(len(data_message))
						size = "0" * (16 - len(size)) + size
						data_message = size.encode("ascii") + data_message
						account = dict()

						for user in accounting_users:
							if user["user"] == username:
								account = user

						if accounting_enable and len(data_message) > int(account["size"]):
							data_message = ""
							message = "425 Can't open data connection."
						else:
							logger(logging_enable, logging_path, "User " + username + " downloaded a file named " + arguments[0])
							account["size"] = str(int(account["size"]) - len(data_message))
							message = "226 Successful Download."

							if account["alert"] and int(account["size"]) < accounting_threshold:
								start_new_thread(send_alert, (account["user"], accounting_threshold, account["email"]))
					else:
						message = "550 File unavailable."
				else:
					message = "500 Error."

			elif command == "HELP":
				message = "214\n"
				message += "USER [name], Its argument is used to specify the user's string. It is used for user authentication.\n"
				message += "PASS [password], Its argument is used to specify the user's password. It is used for user authentication.\n"
				message += "PWD, It is used for printing current working directory\n"
				message += "MKD [flag] [name], Its argument is used to specify the file/directory path. Flag: -i, If present, a new file will be created and otherwise a new directory. It is usede for creating a new file or directory.\n"
				message += "RMD [flag] [name], Its argument is used to specify the file/directory path. Flag: -f, If present, a directory will be removed and otherwise a file. It is usede for removing a file or directory.\n"
				message += "LIST, It is used for printing list of file/directories exists in current working directory\n"
				message += "CWD [path], Its argument is used to specify the directory's path. It is used for changing the current working directory.\n"
				message += "DL [name], Its argument is used to specify the file's name. It is used for downloading a file.\n"
				message += "HELP, It is used for printing list of availibale commands.\n"
				message += "QUIT, It is used for signing out from the server.\n"

			elif command == "QUIT":
				message = "221 Successful Quit."
				break
			else:
				message = "501 Syntax error in parameters or arguments."
		else:
			message = "332 Need account for login."

		command_client.send(message.encode("ascii"))

		if len(data_message) > 0:
			data_client.send(data_message)

	command_client.send(message.encode("ascii"))
	logger(logging_enable, logging_path, "User " + username + " logged out.")
	command_client.close()
	data_client.close()

def main():
	config = rapidjson.loads(open("config.json").read())
	command_channel_port = config["commandChannelPort"]
	data_channel_port = config["dataChannelPort"]
	print("commandChannelPort:", command_channel_port)
	print("dataChannelPort:", data_channel_port)
	logging = config["logging"]
	logging_enable = logging["enable"]
	logging_path = logging["path"]

	if logging_enable:
		log_file = open(logging_path, "a")
		log_file.close()

	host = ""
	command_channel_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	command_channel_sock.bind((host, command_channel_port))
	command_channel_sock.listen()

	data_channel_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	data_channel_sock.bind((host, data_channel_port))
	data_channel_sock.listen()

	while True:
		command_client, command_address = command_channel_sock.accept()
		logger(logging_enable, logging_path, "New client connected to the command channel: " + str(command_address[0]) + ":" + str(command_address[1]))
		data_client, data_address = data_channel_sock.accept()
		logger(logging_enable, logging_path, "New client connected to the data channel: " + str(data_address[0]) + ":" + str(data_address[1]))
		start_new_thread(serve, (command_client, data_client, config))

	command_client.close()
	data_client.close()

if __name__ == "__main__":
	main()