import sqlite3
import os
import shutil

# Đường dẫn thư mục
base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, 'database', 'datalog.db')
static_folder_path = os.path.join(base_dir, 'database', 'static')

def clear_all():
    # 1. Xóa dữ liệu trong database
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('DELETE FROM datalog')
        conn.commit()
        conn.close()
        print("Đã xóa sạch dữ liệu trong bảng 'datalog'.")
    except Exception as e:
        print(f"Lỗi khi xóa database: {e}")

    # 2. Xóa các tệp ảnh trong thư mục static
    if os.path.exists(static_folder_path):
        for filename in os.listdir(static_folder_path):
            file_path = os.path.join(static_folder_path, filename)
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path) # Xóa thư mục con và file bên trong
                else:
                    os.remove(file_path)
            except Exception as e:
                print(f"Không thể xóa {file_path}: {e}")
        print("Đã xóa sạch ảnh trong thư mục 'static'.")

if __name__ == "__main__":
    confirm = input("Bạn có chắc chắn muốn xóa toàn bộ dữ liệu và ảnh? (y/n): ")
    if confirm.lower() == 'y':
        clear_all()
    else:
        print("Đã hủy bỏ.")