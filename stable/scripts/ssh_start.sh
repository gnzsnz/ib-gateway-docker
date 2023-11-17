mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && echo $SSH_PUBLIC_KEY >> ~/.ssh/authorized_keys
service ssh start