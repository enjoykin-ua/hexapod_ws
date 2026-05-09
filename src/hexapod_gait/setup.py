from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'hexapod_gait'

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
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='enjoykin-ua',
    maintainer_email='noreply@gmx.net',
    description='Gait engine for the hexapod (Phase 5).',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'stand_node = hexapod_gait.stand_node:main',
        ],
    },
)
