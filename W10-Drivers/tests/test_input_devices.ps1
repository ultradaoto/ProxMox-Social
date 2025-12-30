# test_input_devices.ps1 - Test Input Device Detection
#
# Verifies that mouse and keyboard devices are properly detected
# and identifies whether they appear as expected hardware.
#
# Usage: Run in PowerShell
#   .\test_input_devices.ps1

$ErrorActionPreference = "SilentlyContinue"

function Write-TestResult {
    param([string]$Test, [bool]$Passed, [string]$Details = "")
    $status = if ($Passed) { "[PASS]" } else { "[FAIL]" }
    $color = if ($Passed) { "Green" } else { "Red" }

    Write-Host "$status $Test" -ForegroundColor $color
    if ($Details) {
        Write-Host "       $Details" -ForegroundColor Gray
    }
}

function Get-HIDDevices {
    Write-Host "`nEnumerating HID Devices..." -ForegroundColor Cyan

    $hidDevices = Get-WmiObject Win32_PnPEntity |
        Where-Object { $_.PNPClass -eq "HIDClass" -or
                      $_.PNPClass -eq "Mouse" -or
                      $_.PNPClass -eq "Keyboard" }

    return $hidDevices
}

function Test-MouseDevices {
    Write-Host "`nTesting Mouse Devices..." -ForegroundColor Cyan

    $mice = Get-WmiObject Win32_PointingDevice

    if (-not $mice) {
        Write-TestResult "Mouse Devices Present" $false "No mouse devices found"
        return $false
    }

    $logitechFound = $false

    foreach ($mouse in $mice) {
        $isLogitech = $mouse.Name -like "*Logitech*" -or
                     $mouse.Description -like "*Logitech*" -or
                     $mouse.PNPDeviceID -like "*VID_046D*"

        if ($isLogitech) {
            $logitechFound = $true
        }

        $status = if ($isLogitech) { "[LOGITECH]" } else { "[OTHER]" }
        $color = if ($isLogitech) { "Green" } else { "Yellow" }

        Write-Host "  $status $($mouse.Name)" -ForegroundColor $color
        Write-Host "          PNP ID: $($mouse.PNPDeviceID)" -ForegroundColor Gray

        if ($mouse.HardwareType) {
            Write-Host "          Type: $($mouse.HardwareType)" -ForegroundColor Gray
        }
    }

    Write-TestResult "Logitech Mouse Detected" $logitechFound

    return $logitechFound
}

function Test-KeyboardDevices {
    Write-Host "`nTesting Keyboard Devices..." -ForegroundColor Cyan

    $keyboards = Get-WmiObject Win32_Keyboard

    if (-not $keyboards) {
        Write-TestResult "Keyboard Devices Present" $false "No keyboard devices found"
        return $false
    }

    $logitechFound = $false

    foreach ($keyboard in $keyboards) {
        $isLogitech = $keyboard.Name -like "*Logitech*" -or
                     $keyboard.Description -like "*Logitech*" -or
                     $keyboard.PNPDeviceID -like "*VID_046D*"

        if ($isLogitech) {
            $logitechFound = $true
        }

        $status = if ($isLogitech) { "[LOGITECH]" } else { "[OTHER]" }
        $color = if ($isLogitech) { "Green" } else { "Yellow" }

        Write-Host "  $status $($keyboard.Name)" -ForegroundColor $color
        Write-Host "          PNP ID: $($keyboard.PNPDeviceID)" -ForegroundColor Gray

        if ($keyboard.Layout) {
            Write-Host "          Layout: $($keyboard.Layout)" -ForegroundColor Gray
        }
    }

    Write-TestResult "Logitech Keyboard Detected" $logitechFound

    return $logitechFound
}

function Test-USBDevices {
    Write-Host "`nTesting USB Device Tree..." -ForegroundColor Cyan

    $usbDevices = Get-WmiObject Win32_USBControllerDevice |
        ForEach-Object {
            [wmi]($_.Dependent)
        } | Where-Object {
            $_.PNPClass -eq "HIDClass" -or
            $_.PNPClass -eq "USB"
        }

    $logitechUSB = $usbDevices | Where-Object {
        $_.DeviceID -like "*VID_046D*"
    }

    if ($logitechUSB) {
        Write-TestResult "Logitech USB Devices" $true "Found $($logitechUSB.Count) Logitech USB devices"

        foreach ($device in $logitechUSB) {
            Write-Host "       $($device.Name)" -ForegroundColor Gray
        }
        return $true
    }
    else {
        Write-TestResult "Logitech USB Devices" $false "No Logitech USB devices in tree"
        return $false
    }
}

function Test-HIDServices {
    Write-Host "`nTesting HID Services..." -ForegroundColor Cyan

    $hidServices = @(
        @{Name = "hidserv"; Display = "Human Interface Device Service"},
        @{Name = "TabletInputService"; Display = "Touch Keyboard and Handwriting Panel Service"}
    )

    $allRunning = $true

    foreach ($svc in $hidServices) {
        $service = Get-Service -Name $svc.Name -ErrorAction SilentlyContinue

        if ($service -and $service.Status -eq "Running") {
            Write-TestResult $svc.Display $true "Running"
        }
        else {
            Write-TestResult $svc.Display $false "Not running or not found"
            $allRunning = $false
        }
    }

    return $allRunning
}

function Test-InputRegistration {
    Write-Host "`nTesting Input Device Registration..." -ForegroundColor Cyan

    # Check raw input device registration
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class RawInput {
    [DllImport("user32.dll")]
    public static extern uint GetRawInputDeviceList(
        IntPtr pRawInputDeviceList,
        ref uint puiNumDevices,
        uint cbSize);
}
"@

    [uint32]$deviceCount = 0
    $structSize = 8 + [IntPtr]::Size  # RAWINPUTDEVICELIST size

    $result = [RawInput]::GetRawInputDeviceList([IntPtr]::Zero, [ref]$deviceCount, $structSize)

    if ($deviceCount -gt 0) {
        Write-TestResult "Raw Input Devices" $true "Found $deviceCount registered devices"
        return $true
    }
    else {
        Write-TestResult "Raw Input Devices" $false "No devices registered"
        return $false
    }
}

function Test-DeviceDrivers {
    Write-Host "`nTesting Device Drivers..." -ForegroundColor Cyan

    $drivers = Get-WmiObject Win32_PnPSignedDriver |
        Where-Object {
            $_.DeviceClass -eq "HIDClass" -or
            $_.DeviceClass -eq "Mouse" -or
            $_.DeviceClass -eq "Keyboard"
        }

    $problemDrivers = $drivers | Where-Object { $_.IsSigned -eq $false }

    if ($problemDrivers) {
        Write-TestResult "Driver Signatures" $false "$($problemDrivers.Count) unsigned drivers"
        foreach ($driver in $problemDrivers) {
            Write-Host "       Unsigned: $($driver.DeviceName)" -ForegroundColor Yellow
        }
        return $false
    }
    else {
        Write-TestResult "Driver Signatures" $true "All drivers are signed"
        return $true
    }
}

function Test-DeviceErrors {
    Write-Host "`nChecking for Device Errors..." -ForegroundColor Cyan

    $problemDevices = Get-WmiObject Win32_PnPEntity |
        Where-Object {
            ($_.PNPClass -eq "HIDClass" -or
             $_.PNPClass -eq "Mouse" -or
             $_.PNPClass -eq "Keyboard") -and
            $_.ConfigManagerErrorCode -ne 0
        }

    if ($problemDevices) {
        Write-TestResult "Device Status" $false "$($problemDevices.Count) devices with errors"
        foreach ($device in $problemDevices) {
            Write-Host "       Error: $($device.Name) - Code $($device.ConfigManagerErrorCode)" -ForegroundColor Red
        }
        return $false
    }
    else {
        Write-TestResult "Device Status" $true "All devices operating normally"
        return $true
    }
}

function Get-DeviceFingerprint {
    Write-Host "`nDevice Fingerprint Analysis:" -ForegroundColor Cyan
    Write-Host "============================" -ForegroundColor Cyan

    $mice = Get-WmiObject Win32_PointingDevice
    $keyboards = Get-WmiObject Win32_Keyboard

    Write-Host "`nMouse fingerprint:" -ForegroundColor Yellow
    foreach ($mouse in $mice) {
        # Extract VID/PID from PNP ID
        if ($mouse.PNPDeviceID -match "VID_([0-9A-F]+)&PID_([0-9A-F]+)") {
            $vid = $matches[1]
            $pid = $matches[2]
            Write-Host "  VID: 0x$vid  PID: 0x$pid" -ForegroundColor White
            Write-Host "  Name: $($mouse.Name)" -ForegroundColor Gray
        }
    }

    Write-Host "`nKeyboard fingerprint:" -ForegroundColor Yellow
    foreach ($keyboard in $keyboards) {
        if ($keyboard.PNPDeviceID -match "VID_([0-9A-F]+)&PID_([0-9A-F]+)") {
            $vid = $matches[1]
            $pid = $matches[2]
            Write-Host "  VID: 0x$vid  PID: 0x$pid" -ForegroundColor White
            Write-Host "  Name: $($keyboard.Name)" -ForegroundColor Gray
        }
    }

    # Expected Logitech values
    Write-Host "`nExpected for Logitech devices:" -ForegroundColor Yellow
    Write-Host "  VID: 0x046D (Logitech)" -ForegroundColor Gray
    Write-Host "  Common PIDs: 0xC52B (Unifying), 0xC534 (Nano), 0xC07D (G502)" -ForegroundColor Gray
}

# Main execution
function Main {
    Write-Host "Input Device Test Suite" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan

    $results = @{
        Mouse = Test-MouseDevices
        Keyboard = Test-KeyboardDevices
        USB = Test-USBDevices
        Services = Test-HIDServices
        RawInput = Test-InputRegistration
        Drivers = Test-DeviceDrivers
        Errors = Test-DeviceErrors
    }

    Get-DeviceFingerprint

    # Summary
    Write-Host "`n=======================" -ForegroundColor Cyan
    Write-Host "Test Summary" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan

    $passed = ($results.Values | Where-Object { $_ }).Count
    $total = $results.Count

    $logitechReady = $results.Mouse -and $results.Keyboard

    Write-Host "`nPassed: $passed / $total tests" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })

    if ($logitechReady) {
        Write-Host "`nLogitech devices detected - VM should appear as real hardware!" -ForegroundColor Green
    }
    else {
        Write-Host "`nNo Logitech devices - check virtual HID setup on Proxmox host" -ForegroundColor Yellow
    }
}

Main
