# Read-only active display inventory. No projection, pairing, firewall or permission changes.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class VitalNativeDisplays {
 [StructLayout(LayoutKind.Sequential)] public struct LUID { public uint Low; public int High; }
 [StructLayout(LayoutKind.Sequential)] public struct Rational { public uint Numerator,Denominator; }
 [StructLayout(LayoutKind.Sequential)] public struct Source { public LUID Adapter; public uint Id,Mode,Status; }
 [StructLayout(LayoutKind.Sequential)] public struct Target { public LUID Adapter; public uint Id,Mode,Technology,Rotation,Scaling;public Rational Refresh;public uint ScanLine;[MarshalAs(UnmanagedType.Bool)]public bool Available;public uint Status; }
 [StructLayout(LayoutKind.Sequential)] public struct PathInfo { public Source Source;public Target Target;public uint Flags; }
 [StructLayout(LayoutKind.Sequential)] public struct Header { public uint Type,Size;public LUID Adapter;public uint Id; }
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] public struct SourceName { public Header Header;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string GdiName; }
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] public struct TargetName { public Header Header;public uint Flags,Technology;public ushort Manufacturer,Product;public uint Instance;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=64)]public string Friendly;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)]public string DevicePath; }
 public class Item { public string Gdi,Label,DevicePath;public uint Technology; }
 [DllImport("user32.dll")]static extern int GetDisplayConfigBufferSizes(uint flags,out uint paths,out uint modes);
 [DllImport("user32.dll")]static extern int QueryDisplayConfig(uint flags,ref uint paths,[Out]PathInfo[] pathInfo,ref uint modes,IntPtr modeInfo,IntPtr topology);
 [DllImport("user32.dll",EntryPoint="DisplayConfigGetDeviceInfo")]static extern int SourceInfo(ref SourceName info);
 [DllImport("user32.dll",EntryPoint="DisplayConfigGetDeviceInfo")]static extern int TargetInfo(ref TargetName info);
 public static Item[] Read() {
  for(int attempt=0;attempt<3;attempt++) {
   uint count,modes;int r=GetDisplayConfigBufferSizes(2,out count,out modes);if(r!=0)throw new Exception("Display inventory unavailable: "+r);
   var paths=new PathInfo[count];IntPtr buffer=Marshal.AllocHGlobal((int)modes*64);
   try {r=QueryDisplayConfig(2,ref count,paths,ref modes,buffer,IntPtr.Zero);if(r==122)continue;if(r!=0)throw new Exception("Display query failed: "+r);var result=new List<Item>();
    for(int i=0;i<count;i++){var p=paths[i];var s=new SourceName();s.Header.Type=1;s.Header.Size=(uint)Marshal.SizeOf(typeof(SourceName));s.Header.Adapter=p.Source.Adapter;s.Header.Id=p.Source.Id;
     var t=new TargetName();t.Header.Type=2;t.Header.Size=(uint)Marshal.SizeOf(typeof(TargetName));t.Header.Adapter=p.Target.Adapter;t.Header.Id=p.Target.Id;
     if(SourceInfo(ref s)==0&&TargetInfo(ref t)==0)result.Add(new Item{Gdi=s.GdiName,Label=t.Friendly,DevicePath=t.DevicePath,Technology=t.Technology});
    }return result.ToArray();
   }finally{Marshal.FreeHGlobal(buffer);}
  }throw new Exception("Display topology changed repeatedly; refresh inventory.");
 }
}
'@
$targets=[VitalNativeDisplays]::Read()
$sha=[System.Security.Cryptography.SHA256]::Create()
$displays=@(foreach($target in $targets){
 $screen=[System.Windows.Forms.Screen]::AllScreens | Where-Object DeviceName -eq $target.Gdi | Select-Object -First 1
 $bytes=[Text.Encoding]::UTF8.GetBytes($target.DevicePath.ToLowerInvariant())
 $stable=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
 [pscustomobject]@{id=$stable;label=$target.Label;gdi=$target.Gdi;technology=$target.Technology;left=if($screen){$screen.Bounds.Left}else{$null};top=if($screen){$screen.Bounds.Top}else{$null};width=if($screen){$screen.Bounds.Width}else{$null};height=if($screen){$screen.Bounds.Height}else{$null};primary=if($screen){$screen.Primary}else{$false};identitySource='Windows display target device path (hashed)'}
})
$sha.Dispose()
[pscustomobject]@{displays=$displays;wirelessConnectionAutomation='not implemented; Windows Win+K pairing remains separate';receiverDiscovery='Only connected active display targets are enumerated'} | ConvertTo-Json -Depth 6 -Compress
