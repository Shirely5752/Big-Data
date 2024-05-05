Backend for Visual Tracking System
**Overview**
This backend serves as the core processing unit for a visual tracking system designed to handle real-time image processing and object tracking through a connected camera device. It utilizes advanced computer vision techniques to detect and track specific colors in real-time, leveraging TensorFlow and OpenCV.
Features
Real-Time Video Processing: Processes video frames received from a serially connected camera to detect objects based on color signatures.
WebSocket Communication: Establishes WebSocket connections to stream processed video frames to connected clients in real-time.
Color Tracking: Dynamically adjusts tracking parameters based on the current tracking color, which is fetched from a Firebase Realtime Database.
Error Handling and Logging: Robust error handling and logging mechanisms to ensure smooth operation and ease of debugging.
**Technologies Used**
Python 3.8+: Primary programming language.
OpenCV: Used for all image processing tasks including color space conversions and object detection.
TensorFlow and TensorFlow Hub: For loading and using pre-trained machine learning models for object detection.
WebSockets: For real-time data streaming to clients.
Firebase: To fetch real-time configuration changes like tracking color.
Asyncio: For handling asynchronous operations, improving the throughput of the system.
**Configuration**
Serial Port Configuration: Ensure that the serial port and baud rate in the script match those of the connected camera device.
Firebase URL: Set your Firebase Realtime Database URL in the script to match your Firebase project settings.
