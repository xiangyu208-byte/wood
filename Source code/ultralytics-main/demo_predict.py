from ultralytics import YOLO


# Load a pretrained YOLOv8 model
yolo = YOLO('yolov8n.pt',task='detect')


# Perform object detection
results = yolo(source='./ultralytics/assets/bus.jpg',save=True,conf=0.1)

# Display the results
results.show()