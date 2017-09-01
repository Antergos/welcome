#!/bin/sh
install -m644 com.antergos.welcomed.service /usr/share/dbus-1/system-services
install -m644 com.antergos.welcomed.conf /etc/dbus-1/system.d
install -m644 com.antergos.welcomed.policy /usr/share/polkit-1/actions
#sudo sed -i "s|USER|${USER}|g" /usr/share/dbus-1/system-services/com.antergos.welcomed.service
