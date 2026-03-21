# edbian-updater
Automatic updater for Edbian

Create package and new version:
git tag v1.0.0
git push origin v1.0.0

mv edbian-installer-v2.deb edbian-installer_${VERSION_CLEAN}_all.deb
