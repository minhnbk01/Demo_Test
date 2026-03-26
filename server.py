import socket
import threading
import datetime
import os

class ChatServer:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Quản lý trạng thái
        self.clients = {}  # {username: {"socket": conn, "is_admin": bool}}
        self.lock = threading.Lock() # Bảo vệ self.clients
        
        self.admin_password = "admin"
        self.ban_file = "bans.txt"
        
        # Đảm bảo file ban tồn tại
        if not os.path.exists(self.ban_file):
            open(self.ban_file, 'w').close()

    def log(self, message):
        """Ghi log hệ thống vào file và in ra console"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open("server.log", "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")

    def is_banned(self, username):
        with open(self.ban_file, "r") as f:
            banned_users = f.read().splitlines()
        return username in banned_users

    def ban_user(self, username):
        with open(self.ban_file, "a") as f:
            f.write(username + "\n")

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen()
            self.log(f"Server đang chạy tại {self.host}:{self.port}...")
        except OSError as e:
            if e.errno == 10048: # WinError 10048: Trùng Port
                print("Lỗi: Port này đã được sử dụng. Hãy kiểm tra lại!")
            return

        while True:
            conn, addr = self.server_socket.accept()
            thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            thread.start()

    def handle_client(self, conn, addr):
        self.log(f"Kết nối mới từ {addr}")
        username = None
        is_admin = False

        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                
                message = data.decode('utf-8').strip()
                if not message:
                    continue

                parts = message.split(' ', 1)
                command = parts[0]

                # Xử lý khi chưa đăng nhập
                if not username:
                    if command == "/login":
                        if len(parts) < 2:
                            conn.send("Lỗi: Cú pháp /login <username> [password]\n".encode())
                            continue
                        
                        login_info = parts[1].split(' ', 1)
                        req_username = login_info[0]

                        if self.is_banned(req_username):
                            conn.send("Bạn đã bị khóa khỏi máy chủ.\n".encode())
                            break

                        with self.lock:
                            if req_username in self.clients:
                                conn.send("Tên đăng nhập đã tồn tại.\n".encode())
                                continue
                            
                            # Kiểm tra Admin
                            if req_username.lower() == "admin":
                                if len(login_info) < 2 or login_info[1] != self.admin_password:
                                    conn.send("Sai mật khẩu Admin.\n".encode())
                                    continue
                                is_admin = True

                            username = req_username
                            self.clients[username] = {"socket": conn, "is_admin": is_admin}
                        
                        role = "ADMIN" if is_admin else "USER"
                        conn.send(f"Đăng nhập thành công với tư cách {role}.\n".encode())
                        self.log(f"{username} đã đăng nhập.")
                    else:
                        conn.send("Vui lòng đăng nhập bằng: /login <username>\n".encode())
                    continue

                # ROUTING: Bộ điều hướng lệnh sau khi đăng nhập
                if command == "/list":
                    with self.lock:
                        online_users = ", ".join(self.clients.keys())
                    conn.send(f"Online: {online_users}\n".encode())

                elif command == "/all":
                    if len(parts) < 2:
                        conn.send("Cú pháp: /all <nội dung>\n".encode())
                        continue
                    self.broadcast(f"[ALL] {username}: {parts[1]}", sender=username)

                elif command == "/msg":
                    if len(parts) < 2:
                        conn.send("Cú pháp: /msg <username> <nội dung>\n".encode())
                        continue
                    msg_parts = parts[1].split(' ', 1)
                    if len(msg_parts) < 2:
                        conn.send("Cú pháp: /msg <username> <nội dung>\n".encode())
                        continue
                    self.send_private(msg_parts[0], f"[Private từ {username}]: {msg_parts[1]}", conn)

                elif command == "/kick" or command == "/ban":
                    if not is_admin:
                        conn.send("Lỗi: Chỉ Admin mới có quyền này.\n".encode())
                        continue
                    if len(parts) < 2:
                        conn.send(f"Cú pháp: {command} <username>\n".encode())
                        continue
                    target_user = parts[1]
                    self.kick_user(target_user, ban=(command == "/ban"))

                elif command == "/quit":
                    break
                else:
                    conn.send("Lệnh không hợp lệ.\n".encode())

        except ConnectionResetError:
            # WinError 10054: Client tắt đột ngột (rút dây mạng, tắt console chữ X)
            self.log(f"Mất kết nối đột ngột từ {addr}")
        except Exception as e:
            self.log(f"Lỗi Client {addr}: {str(e)}")
        finally:
            # DỌN DẸP GHOST CLIENT
            if username:
                with self.lock:
                    if username in self.clients:
                        del self.clients[username]
                self.log(f"{username} đã thoát.")
                self.broadcast(f"Hệ thống: {username} đã rời phòng.", sender=None)
            conn.close()

    def broadcast(self, message, sender=None):
        with self.lock:
            for user, info in self.clients.items():
                if user != sender:
                    try:
                        info["socket"].send((message + "\n").encode('utf-8'))
                    except:
                        pass

    def send_private(self, target_user, message, sender_conn):
        with self.lock:
            if target_user in self.clients:
                try:
                    self.clients[target_user]["socket"].send((message + "\n").encode('utf-8'))
                except:
                    pass
            else:
                sender_conn.send(f"Lỗi: User '{target_user}' không online.\n".encode())

    def kick_user(self, target_user, ban=False):
        with self.lock:
            if target_user in self.clients:
                target_conn = self.clients[target_user]["socket"]
                try:
                    msg = "Bạn đã bị BAN vĩnh viễn!" if ban else "Bạn đã bị KICK khỏi máy chủ!"
                    target_conn.send((msg + "\n").encode('utf-8'))
                    target_conn.close() # Cắt kết nối ngay lập tức
                except:
                    pass
                if ban:
                    self.ban_user(target_user)
                    self.log(f"Admin đã BAN {target_user}")
                else:
                    self.log(f"Admin đã KICK {target_user}")
                self.broadcast(f"Hệ thống: {target_user} đã bị {'BAN' if ban else 'KICK'} bởi Admin.")

if __name__ == "__main__":
    server = ChatServer()
    server.start()