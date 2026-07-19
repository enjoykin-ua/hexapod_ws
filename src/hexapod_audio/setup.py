from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'hexapod_audio'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
        (os.path.join('share', package_name, 'sounds'),
            glob('sounds/*.mp3')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='enjoykin-ua',
    maintainer_email='noreply@gmx.net',
    description='Audio-Ausgabe (mp3 auf dem Roboter-Speaker) für den Hexapod '
                '(Block I Phase 7A).',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'hexapod_audio = hexapod_audio.audio_node:main',
        ],
    },
)
