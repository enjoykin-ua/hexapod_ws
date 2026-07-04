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
        # Phase 11 Stage D — Gait-Preset-YAMLs (D-Q2 Option A) +
        # presets/README.md
        (os.path.join('share', package_name, 'config', 'presets'),
            glob('config/presets/*.yaml') + glob('config/presets/*.md')),
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
            'gait_node = hexapod_gait.gait_node:main',
            'reachability_viz = hexapod_gait.reachability_viz:main',
            'torque_viz = hexapod_gait.torque_viz:main',
            'foot_contact_viz = hexapod_gait.foot_contact_viz:main',
            'pose_publisher = hexapod_gait.pose_publisher:main',
        ],
    },
)
