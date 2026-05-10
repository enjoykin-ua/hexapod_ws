from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'hexapod_teleop'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='enjoykin',
    maintainer_email='andrej.kra@gmx.net',
    description=(
        'Teleop-Knoten für den Hexapod: PS4-Controller (Stufe A, USB) '
        'und später BT (Stufe B). Konsumiert /joy, publisht /cmd_vel + '
        '/cmd_body_height.'
    ),
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'joy_to_twist = hexapod_teleop.joy_to_twist:main',
        ],
    },
)
