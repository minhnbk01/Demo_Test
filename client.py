import socket
import threading
import sys

class ChatClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_running = True

    def start(self):
        try:
            self.client_socket.connect((self.host, self.port))
        except ConnectionRefusedError:
            # WinError 10061: Server chưa bật
            print("Lỗi: Không thể kết nối. Máy chủ chưa bật hoặc sai địa chỉ IP/Port.")
            return

        print("Kết nối thành công! Vui lòng gõ: /login <username> [mật_khẩu_admin]")
        
        # Tách luồng nhận tin nhắn thành Daemon
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()

        # Luồng chính (Main Thread) xử lý việc gửi lệnh
        try:
            while self.is_running:
                message = input(">> ")
                if not message:
                    continue
                
                self.client_socket.send(message.encode('utf-8'))
                
                if message == "/quit":
                    self.is_running = False
                    break
        except KeyboardInterrupt:
            # Xử lý khi user bấm Ctrl+C
            self.client_socket.send("/quit".encode('utf-8'))
        finally:
            print("Đang đóng kết nối...")
            self.client_socket.close()

    def receive_messages(self):
        while self.is_running:
            try:
                data = self.client_socket.recv(1024)
                if not data:
                    print("\nBị ngắt kết nối từ máy chủ.")
                    self.is_running = False
                    # Ngắt input hiện tại để thoát
                    sys.exit(0)
                
                message = data.decode('utf-8').strip()
                
                # TRICK XỬ LÝ UI: Dọn dẹp dòng hiện tại và in lại dấu nhắc lệnh
                # \r lùi về đầu dòng, chèn khoảng trắng để xóa dòng, rồi lùi về đầu lần nữa
                sys.stdout.write('\r' + ' ' * 50 + '\r')
                print(message)
                sys.stdout.write('>> ')
                sys.stdout.flush() # Bắt buộc flush để ép console hiển thị ngay lập tức

            except ConnectionResetError:
                print("\nMáy chủ đã đột ngột đóng kết nối.")
                self.is_running = False
                sys.exit(0)
            except OSError:
                # Xảy ra khi socket bị đóng ở luồng chính
                break

if __name__ == "__main__":
    client = ChatClient()
    client.start()