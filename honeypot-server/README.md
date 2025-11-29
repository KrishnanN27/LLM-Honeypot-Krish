## Start server

> python main.py

## Connect with SSH

> ssh -T -p 2222 "root@localhost"python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
