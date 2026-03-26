import socket
import threading
import sys
import os

class ChatClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = True

    def receive_messages(self):
        """GĐ 4: Daemon Thread lắng nghe tin nhắn và xử lý UI Console mượt mà"""
        while self.running:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if not message:
                    print("\n[HỆ THỐNG] Ngắt kết nối từ Server.")
                    self.running = False
                    os._exit(0) # Thoát ngay lập tức
                
                # Trick xử lý UI Console: Xóa dòng nhắc lệnh hiện tại, in tin nhắn, in lại nhắc lệnh
                sys.stdout.write('\r' + ' ' * 50 + '\r') 
                print(message)
                sys.stdout.write('>> ')
                sys.stdout.flush()

            except ConnectionResetError:
                # WinError 10054: Server tắt đột ngột
                print("\n[HỆ THỐNG] Mất kết nối tới Server (Server down).")
                self.running = False
                os._exit(0)
            except Exception:
                self.running = False
                break

    def start(self):
        try:
            self.client_socket.connect((self.host, self.port))
        except ConnectionRefusedError:
            # WinError 10061: Không tìm thấy Server
            print("[ERROR] Không thể kết nối! Hãy chắc chắn Server đã được bật.")
            return

        # GĐ 2: Xử lý vòng lặp đăng nhập
        print("=== CHÀO MỪNG ĐẾN VỚI TCP CHAT CONSOLE ===")
        while True:
            username = input("Nhập username: ")
            if username.lower() == 'admin':
                password = input("Nhập mật khẩu Admin: ")
                login_cmd = f"/login {username} {password}"
            else:
                login_cmd = f"/login {username}"
            
            self.client_socket.send(login_cmd.encode('utf-8'))
            response = self.client_socket.recv(1024).decode('utf-8')
            print(response)
            
            if "[SUCCESS]" in response:
                break
            if "[ERROR]" in response and "BAN" in response:
                self.client_socket.close()
                return

        # GĐ 4: Khởi chạy luồng nhận tin nhắn (Daemon)
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()

        # Luồng chính (Main Thread) xử lý gửi lệnh
        print("\nCác lệnh hỗ trợ: /list, /all <tin nhắn>, /msg <username> <tin nhắn>, /quit")
        if username.lower() == 'admin':
            print("Lệnh Admin: /kick <username>, /ban <username>")

        try:
            while self.running:
                sys.stdout.write('>> ')
                sys.stdout.flush()
                command = input()
                
                if command.strip() == '':
                    continue

                self.client_socket.send(command.encode('utf-8'))
                
                if command == '/quit':
                    self.running = False
                    break
        except Exception:
            pass
        finally:
            self.client_socket.close()

if __name__ == "__main__":
    client = ChatClient()
    client.start()