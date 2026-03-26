import socket
import threading
import datetime
import os

class ChatServer:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.clients = {}
        self.lock = threading.Lock()
        self.admin_password = "admin"
        self.ban_file = "bans.txt"
        self.log_file = "server.log"
        if not os.path.exists(self.ban_file):
            open(self.ban_file, 'w').close()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def log_activity(self, message):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')

    def is_banned(self, username):
        with open(self.ban_file, 'r', encoding='utf-8') as f:
            banned_users = f.read().splitlines()
        return username in banned_users

    def ban_user(self, username):
        with open(self.ban_file, 'a', encoding='utf-8') as f:
            f.write(username + '\n')

    def broadcast(self, message, sender_socket=None):
        with self.lock:
            for user, client in self.clients.items():
                if client != sender_socket:
                    try:
                        client.send(message.encode('utf-8'))
                    except:
                        pass

    def remove_client(self, username, announce=True):
        with self.lock:
            client = self.clients.pop(username, None)
        if client:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()
            self.log_activity(f"User '{username}' đã rời phòng.")
            if announce:
                self.broadcast(f"[SERVER] {username} đã rời phòng.")

    def handle_client(self, client_socket, address):
        username = None
        try:
            while True:
                login_msg = client_socket.recv(1024).decode('utf-8')
                parts = login_msg.split(' ', 2)
                if len(parts) >= 2 and parts[0] == '/login':
                    temp_user = parts[1]
                    if self.is_banned(temp_user):
                        client_socket.send("[ERROR] Tài khoản của bạn đã bị BAN vĩnh viễn!".encode('utf-8'))
                        return
                    with self.lock:
                        if temp_user in self.clients:
                            client_socket.send("[ERROR] Username đã tồn tại. Thử lại!".encode('utf-8'))
                            continue
                    if temp_user.lower() == "admin":
                        if len(parts) < 3 or parts[2] != self.admin_password:
                            client_socket.send("[ERROR] Sai mật khẩu Admin!".encode('utf-8'))
                            continue
                    username = temp_user
                    with self.lock:
                        self.clients[username] = client_socket
                    client_socket.send("[SUCCESS] Đăng nhập thành công!".encode('utf-8'))
                    self.log_activity(f"Client {address} đăng nhập với tên '{username}'.")
                    self.broadcast(f"[SERVER] {username} đã tham gia phòng chat!")
                    break

            while True:
                message = client_socket.recv(1024).decode('utf-8')
                if not message:
                    break
                self.log_activity(f"[{username}] gửi lệnh: {message}")
                parts = message.split(' ', 1)
                command = parts[0]
                if command == '/list':
                    with self.lock:
                        users = ", ".join(self.clients.keys())
                    client_socket.send(f"[SERVER] Danh sách Online: {users}".encode('utf-8'))
                elif command == '/all':
                    if len(parts) > 1:
                        self.broadcast(f"[ALL] {username}: {parts[1]}", client_socket)
                    else:
                        client_socket.send("[SYSTEM] Lỗi: Tham số không hợp lệ. Dùng: /all <nội dung>".encode('utf-8'))
                elif command == '/msg':
                    sub_parts = parts[1].split(' ', 1) if len(parts) > 1 else []
                    if len(sub_parts) == 2:
                        target, content = sub_parts
                        with self.lock:
                            target_sock = self.clients.get(target)
                        if target_sock:
                            target_sock.send(f"[PRIVATE từ {username}]: {content}".encode('utf-8'))
                        else:
                            client_socket.send(f"[SERVER] Không tìm thấy user '{target}'.".encode('utf-8'))
                    else:
                        client_socket.send("[SYSTEM] Lỗi: Dùng /msg <username> <nội dung>".encode('utf-8'))
                elif command in ['/kick', '/ban']:
                    if username.lower() != 'admin':
                        client_socket.send("[SERVER] Lỗi: Bạn không có quyền thực hiện lệnh này.".encode('utf-8'))
                        continue
                    if len(parts) > 1:
                        target = parts[1]
                        with self.lock:
                            target_sock = self.clients.get(target)
                        if target_sock:
                            try:
                                target_sock.send("[SERVER] Bạn đã bị đuổi khỏi phòng!".encode('utf-8'))
                            except Exception:
                                pass
                            if command == '/ban':
                                self.ban_user(target)
                                self.broadcast(f"[SERVER] Admin đã BAN vĩnh viễn {target}.")
                            else:
                                self.broadcast(f"[SERVER] Admin đã KICK {target}.")
                            self.remove_client(target, announce=False)
                        else:
                            client_socket.send(f"[SERVER] Không tìm thấy user '{target}'.".encode('utf-8'))
                    else:
                        client_socket.send(f"[SYSTEM] Lỗi: Dùng {command} <username>".encode('utf-8'))
                elif command == '/quit':
                    client_socket.send("[SERVER] Tạm biệt!".encode('utf-8'))
                    break
                else:
                    client_socket.send("[SERVER] Lệnh không hợp lệ.".encode('utf-8'))
        except ConnectionResetError:
            self.log_activity(f"Cảnh báo: Client {address} (User: {username}) mất kết nối đột ngột")
        except Exception as e:
            self.log_activity(f"Lỗi không xác định với {username}: {e}")
        finally:
            if username:
                self.remove_client(username)
            else:
                client_socket.close()

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.log_activity(f"Server đang chạy tại {self.host}:{self.port}")
            
            while True:
                client_socket, address = self.server_socket.accept()
                self.log_activity(f"Chấp nhận kết nối từ {address}")
                # Đẩy việc xử lý cho luồng riêng
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                client_thread.start()
        except OSError:
            # Lỗi WinError 10048: Cổng đã được sử dụng
            print(f"[ERROR] Port {self.port} đã bị chiếm dụng. Vui lòng đổi Port khác!")
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    server = ChatServer()
    server.start()