<#
.SYNOPSIS
    Forces the primary display resolution to 1600x1200.
    Required for consistent VNC automation (TightVNC).

.DESCRIPTION
    Uses C# P/Invoke to call User32.dll ChangeDisplaySettings.
    This bypasses GUI limitations if the monitor EDID supports the resolution.
#>

$code = @'
using System;
using System.Runtime.InteropServices;

public class Resolution {
    [DllImport("user32.dll")]
    public static extern int ChangeDisplaySettings(ref DEVMODE devMode, int flags);

    [DllImport("user32.dll")]
    public static extern bool EnumDisplaySettings(string deviceName, int modeNum, ref DEVMODE devMode);

    [StructLayout(LayoutKind.Sequential)]
    public struct DEVMODE {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string dmDeviceName;
        public short dmSpecVersion;
        public short dmDriverVersion;
        public short dmSize;
        public short dmDriverExtra;
        public int dmFields;
        public int dmPositionX;
        public int dmPositionY;
        public int dmDisplayOrientation;
        public int dmDisplayFixedOutput;
        public short dmColor;
        public short dmDuplex;
        public short dmYResolution;
        public short dmTTOption;
        public short dmCollate;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string dmFormName;
        public short dmLogPixels;
        public int dmBitsPerPel;
        public int dmPelsWidth;
        public int dmPelsHeight;
        public int dmDisplayFlags;
        public int dmDisplayFrequency;
        public int dmICMMethod;
        public int dmICMIntent;
        public int dmMediaType;
        public int dmDitherType;
        public int dmReserved1;
        public int dmReserved2;
        public int dmPanningWidth;
        public int dmPanningHeight;
    }

    public static void SetResolution(int width, int height) {
        DEVMODE dm = new DEVMODE();
        dm.dmDeviceName = new String(new char[32]);
        dm.dmFormName = new String(new char[32]);
        dm.dmSize = (short)Marshal.SizeOf(dm);

        if (EnumDisplaySettings(null, -1, ref dm)) {
            dm.dmPelsWidth = width;
            dm.dmPelsHeight = height;
            dm.dmFields = 0x80000 | 0x100000; // DM_PELSWIDTH | DM_PELSHEIGHT

            int iRet = ChangeDisplaySettings(ref dm, 0);
            if (iRet == 0) {
                Console.WriteLine("Resolution set to " + width + "x" + height + " successfully.");
            } else {
                Console.WriteLine("Failed to set resolution. Error code: " + iRet);
            }
        }
    }
}
'@

Add-Type -TypeDefinition $code -Language CSharp

Write-Host "Setting resolution to 1600x1200..." -ForegroundColor Cyan
[Resolution]::SetResolution(1600, 1200)
