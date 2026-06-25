from setuptools import find_packages, setup


package_name = 'hexapod_sensors'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='enjoykin-ua',
    maintainer_email='noreply@gmx.net',
    description='Sensor-Adapter (Sim/HW-Bridge) für den Hexapod (Phase 5+).',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'foot_contact_publisher = '
            'hexapod_sensors.foot_contact_publisher:main',
            'imu_monitor = hexapod_sensors.imu_monitor:main',
        ],
    },
)
