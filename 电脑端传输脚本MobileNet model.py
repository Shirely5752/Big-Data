import asyncio
import traceback
import websockets
import cv2
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from threading import Thread
import serial
import queue
import base64
import requests
import json
import time
import logging

logging.basicConfig(level=logging.INFO)

# Firebase Realtime Database URL
FIREBASE_URL = 'https://sspu-thesis-default-rtdb.europe-west1.firebasedatabase.app/'

# 初始化串行通信
ser = serial.Serial('COM5', 460800, timeout=1)
frame_queue = queue.Queue(maxsize=2)

# 定义颜色的HSV范围
color_ranges = {
    'orange': (np.array([11, 100, 100]), np.array([25, 255, 255])),
    'blue': (np.array([110, 100, 20]), np.array([130, 255, 255])),
    'pink': (np.array([160, 100, 100]), np.array([180, 255, 255])),
    'green': (np.array([35, 100, 50]), np.array([85, 255, 255])),
    'white': (np.array([0, 0, 231]), np.array([180, 25, 255])),
    'black': (np.array([0, 0, 0]), np.array([180, 255, 30]))
}


# 初始化WebSocket连接集合
connected = set()


async def register(websocket):
    print("WebSocket connection established.")
    connected.add(websocket)


async def unregister(websocket):
    print("WebSocket connection closed")
    connected.remove(websocket)


async def video_stream(websocket, path):
    await register(websocket)
    try:
        while True:
            await asyncio.sleep(0.1)  # 仅用于保持连接
    finally:
        await unregister(websocket)


def read_from_port(ser):
    logging_output_enabled = False  # 将此设置为False以禁用帧开始/结束日志
    try:
        while True:
            if ser.read_until(b'FRAME_START'):
                if logging_output_enabled:
                    print("Frame start detected.")
                img_size_bytes = ser.read(4)
                img_size = int.from_bytes(img_size_bytes, 'little')
                img_bytes = ser.read(img_size)
                if ser.read_until(b'FRAME_END') and len(img_bytes) == img_size:
                    if logging_output_enabled:
                        print(f"Frame end detected, frame size: {img_size}")
                    if not frame_queue.full():
                        frame_queue.put(img_bytes)
                else:
                    if logging_output_enabled:
                        print("Incomplete frame detected.")
    except Exception as e:
        print("Exception in read_from_port:", e)
        traceback.print_exc()


# 加载预训练的SSD MobileNet V2模型
detector = hub.load("https://tfhub.dev/tensorflow/ssd_mobilenet_v2/2")


def fetch_current_color():
    global current_color
    first_fetch = True
    while True:
        try:
            response = requests.get(FIREBASE_URL + '/trackingColor/color.json')
            if response.status_code == 200:
                new_color = response.json()
                if new_color and (first_fetch or new_color != current_color):
                    current_color = new_color
                    first_fetch = False
                    print(
                        f"### Tracking color updated to: {current_color} ###")
            else:
                print("Failed to fetch current color")
        except Exception as e:
            print(f"Error fetching color: {e}")
        time.sleep(1)  # 每秒查询一次


# async def send_frames():
#     try:
#         while True:
#             await asyncio.sleep(0.033)  # 控制发送频率为每秒约30帧
#             if not frame_queue.empty():
#                 img_bytes = frame_queue.get()
#                 img_array = np.frombuffer(img_bytes, dtype=np.uint8)
#                 img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
#                 if img is not None:
#                     _, buffer = cv2.imencode(
#                         '.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
#                     img_bytes = buffer.tobytes()
#                     for ws in connected:
#                         await ws.send(img_bytes)
#     except Exception as e:
#         logging.error("Exception in send_frames:", exc_info=True)
async def send_frames():
    try:
        while True:
            await asyncio.sleep(0.033)  # 控制发送频率为每秒约30帧
            if not frame_queue.empty():
                img_bytes = frame_queue.get()
                img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if img is not None:
                    # 在发送之前对图像进行处理
                    img_processed = detect_and_draw(img)
                    # 对处理后的图像进行编码
                    _, buffer = cv2.imencode('.jpg', img_processed, [
                                             int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    img_bytes_processed = buffer.tobytes()
                    for ws in connected:
                        await ws.send(img_bytes_processed)
    except Exception as e:
        logging.error("Exception in send_frames:", exc_info=True)


def detect_and_draw(img):
    global current_color
    # 转换图像到HSV色彩空间
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    mask = None  # 在这里初始化mask

    # 调整图像大小为模型输入所需的尺寸
    img_resized = cv2.resize(img, (320, 320))
    input_tensor = tf.convert_to_tensor(img_resized, dtype=tf.uint8)
    input_tensor = input_tensor[tf.newaxis, ...]

    # 进行检测
    detector_output = detector(input_tensor)

    # 提取检测结果
    result = {key: value.numpy() for key, value in detector_output.items()}
    detection_boxes = result['detection_boxes']
    detection_scores = result['detection_scores']
    detection_classes = result['detection_classes']

    h, w, _ = img.shape
    for i in range(detection_scores.shape[1]):
        if detection_scores[0, i] >= 0.61 and detection_classes[0, i] == 1:
            box = detection_boxes[0, i]
            ymin, xmin, ymax, xmax = box
            (left, right, top, bottom) = (xmin * w, xmax * w, ymin * h, ymax * h)
            left, right, top, bottom = int(left), int(
                right), int(top), int(bottom)

            # 定义ROI
            roi = hsv_img[top:bottom, left:right]

            # 使用当前颜色进行追踪
            lower, upper = color_ranges[current_color]
            mask = cv2.inRange(roi, lower, upper)

    if mask is not None:  # 确保mask已经被赋值
        print(
            f"Current tracking color: {current_color}, HSV range: {color_ranges[current_color]}")
        non_zero_pixels = cv2.countNonZero(mask)
        print(f"Non-zero pixels in mask: {non_zero_pixels}")

        if non_zero_pixels > 0:
            print("Detected the tracking color, drawing red rectangle.")
            cv2.rectangle(img, (left, top), (right, bottom), (0, 0, 255), 2)
        else:
            print("Did not detect the tracking color, drawing green rectangle.")
            cv2.rectangle(img, (left, top), (right, bottom), (0, 255, 0), 2)

    return img


def start_websocket_server():
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        start_server = websockets.serve(video_stream, "0.0.0.0", 8765)

        # 在WebSocket服务器启动之后，创建并启动send_frames任务
        loop.run_until_complete(start_server)
        loop.create_task(send_frames())  # 创建并调度send_frames协程任务

        print("WebSocket server running on ws://0.0.0.0:8765")
        loop.run_forever()  # 启动事件循环
    except Exception as e:
        print("Exception in start_websocket_server:", e)
        traceback.print_exc()


# 启动WebSocket服务器线程
ws_thread = Thread(target=start_websocket_server, daemon=True)
ws_thread.start()


# 启动Firebase颜色更新监听线程
color_fetch_thread = Thread(target=fetch_current_color, daemon=True)
color_fetch_thread.start()


def display_frames():
    print("Display frames function called.")
    while True:
        if not frame_queue.empty():
            img_bytes = frame_queue.get()
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img is not None:
                img = detect_and_draw(img)
                cv2.imshow("OpenMV Stream", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break


thread = Thread(target=read_from_port, args=(ser,))
thread.start()

display_frames()
