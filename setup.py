from setuptools import setup

setup(
    name='gns3-converter',
    version='0.1.0',
    packages=['gns3converter'],
    url='https://github.com/dlintott/gns3-converter',
    license='GNU General Public License v3 (GPLv3)',
    author='Daniel Lintott',
    author_email='daniel@serverb.co.uk',
    description='Convert old ini-style GNS3 topologies (<=0.8.7) to the '
                'newer version 1+ JSON format',
    test_suite='tests',
    install_requires=['configobj'],
    package_data={'gns3converter': ['configspec']},
    entry_points={'console_scripts': ['converter = gns3converter.main:main']},
    classifiers=['Development Status :: 4 - Beta',
                 'Environment :: Console',
                 'Intended Audience :: Education',
                 'Intended Audience :: Information Technology',
                 'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
                 'Natural Language :: English',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python :: 3',
                 'Programming Language :: Python :: 3.3',
                 'Programming Language :: Python :: 3.4',
                 'Topic :: Education',
                 'Topic :: Utilities']
)