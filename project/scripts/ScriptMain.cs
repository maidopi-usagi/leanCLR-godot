using Godot;

namespace Game;

public partial class ScriptMain : Node2D
{
    [Export(PropertyHint.Range, "0,1000,1")]
    public int InspectorNumber { get; set; } = 7;

    private bool processPrinted;
    private bool physicsProcessPrinted;
    private bool inputPrinted;
    private bool guiInputPrinted;

    public override void _EnterTree()
    {
        GD.Print("LeanCLR demo: _EnterTree owner name = " + Name);
    }

    public override void _ExitTree()
    {
        GD.Print("LeanCLR demo: _ExitTree owner name = " + Name);
    }

    public override void _Ready()
    {
        StringName ownerName = Name;
        GD.Print("LeanCLR demo: ScriptLanguage owner name = " + ownerName.ToString());
        Position = new Vector2(12.0f, 34.0f);
        Scale = new Vector2(2.0f, 3.0f);
        SetModulate(new Color(0.25f, 0.5f, 0.75f, 1.0f));
        Color modulate = GetModulate();
        GD.Print("LeanCLR demo: position = " + Position.ToString());
        GD.Print("LeanCLR demo: scale = " + Scale.ToString());
        GD.Print("LeanCLR demo: modulate color = " + modulate.ToString());
        Label label = GetNode<Label>(new NodePath("UiLabel"));
        label.Text = "LeanCLR Label";
        label.Position = new Vector2(7.0f, 8.0f);
        label.Size = new Vector2(120.0f, 24.0f);
        label.SetHorizontalAlignment(HorizontalAlignment.Center);
        label.SetHSizeFlags(Control.SizeFlags.SizeExpandFill);
        label.SetJustificationFlags(TextServer.JustificationFlag.JustificationWordBound | TextServer.JustificationFlag.JustificationTrimEdgeSpaces);
        label.Hide();
        label.Show();
        GD.Print("LeanCLR demo: label text = " + label.Text);
        GD.Print("LeanCLR demo: label position = " + label.Position.ToString());
        GD.Print("LeanCLR demo: label h alignment = " + label.GetHorizontalAlignment().ToString());
        GD.Print("LeanCLR demo: label h size flags = " + label.GetHSizeFlags().ToString());
        GD.Print("LeanCLR demo: label justification flags = " + label.GetJustificationFlags().ToString());
        GD.Print("LeanCLR demo: label rect = " + label.GetRect().ToString());
        GD.Print("LeanCLR demo: node2d transform = " + GetTransform().ToString());
        GD.Print("LeanCLR demo: label canvas RID valid = " + label.GetCanvasItem().IsValid().ToString());
        Font defaultFont = label.GetThemeDefaultFont();
        GD.Print("LeanCLR demo: label default font exists = " + (defaultFont != null).ToString());
        Font defaultFontAgain = label.GetThemeDefaultFont();
        GD.Print("LeanCLR demo: wrapper identity cache = " + object.ReferenceEquals(defaultFont, defaultFontAgain).ToString());
        if (defaultFont != null)
        {
            defaultFont.Dispose();
        }
        GD.Print("LeanCLR demo: label visible = " + label.IsVisible().ToString());
        GD.Print("LeanCLR demo: script property initial = " + Get(new StringName("InspectorNumber")).AsInt64().ToString());
        Set(new StringName("InspectorNumber"), new Variant(314));
        GD.Print("LeanCLR demo: script property updated = " + InspectorNumber.ToString());
        GodotArray scriptProperties = GetPropertyList();
        GD.Print("LeanCLR demo: script property list exists = " + (scriptProperties != null).ToString());
        if (scriptProperties != null)
        {
            for (int i = 0; i < scriptProperties.Count; ++i)
            {
                Dictionary propertyInfo = scriptProperties[i].AsDictionary();
                if (propertyInfo[new Variant("name")].ToString() == "InspectorNumber")
                {
                    GD.Print("LeanCLR demo: script property hint = " + propertyInfo[new Variant("hint")].ToString());
                    GD.Print("LeanCLR demo: script property hint string = " + propertyInfo[new Variant("hint_string")].ToString());
                }
            }
            scriptProperties.Dispose();
        }
        string sceneUniqueId = Resource.GenerateSceneUniqueId();
        GD.Print("LeanCLR demo: resource id length > 0 = " + (sceneUniqueId.Length > 0).ToString());
        Variant metaValue = new Variant("LeanCLR Variant");
        SetMeta(new StringName("leanclr_meta"), metaValue);
        GD.Print("LeanCLR demo: variant meta exists = " + HasMeta(new StringName("leanclr_meta")).ToString());
        Variant metaRoundtrip = GetMeta(new StringName("leanclr_meta"));
        GD.Print("LeanCLR demo: variant meta = " + metaRoundtrip.ToString());
        metaRoundtrip.Dispose();
        metaValue.Dispose();
        Variant callMetaKey = new Variant("leanclr_call_meta");
        Variant callMetaValue = new Variant("LeanCLR Call Variant");
        Call(new StringName("set_meta"), callMetaKey, callMetaValue).Dispose();
        Variant callMetaRoundtrip = Call(new StringName("get_meta"), callMetaKey);
        GD.Print("LeanCLR demo: object call variant meta = " + callMetaRoundtrip.ToString());
        callMetaRoundtrip.Dispose();
        callMetaValue.Dispose();
        callMetaKey.Dispose();
        AddToGroup(new StringName("leanclr_vararg_group"));
        Variant groupMetaKey = new Variant("leanclr_group_meta");
        Variant groupMetaValue = new Variant("LeanCLR Group Variant");
        GetTree().CallGroup(new StringName("leanclr_vararg_group"), new StringName("set_meta"), groupMetaKey, groupMetaValue);
        Variant groupMetaRoundtrip = GetMeta(new StringName("leanclr_group_meta"));
        GD.Print("LeanCLR demo: call group variant meta = " + groupMetaRoundtrip.ToString());
        groupMetaRoundtrip.Dispose();
        groupMetaValue.Dispose();
        groupMetaKey.Dispose();
        Variant jsonValue = new Variant("LeanCLR JSON");
        string jsonText = JSON.Stringify(jsonValue);
        GD.Print("LeanCLR demo: variant json = " + jsonText);
        jsonValue.Dispose();
        Variant parsedJson = JSON.ParseString("123");
        GD.Print("LeanCLR demo: parsed variant = " + parsedJson.ToString());
        parsedJson.Dispose();
        GD.Print("LeanCLR demo: project file exists = " + FileAccess.FileExists("res://project.godot").ToString());
        GD.Print("LeanCLR demo: project file text length > 0 = " + (FileAccess.GetFileAsString("res://project.godot").Length > 0).ToString());
        PackedByteArray projectBytes = FileAccess.GetFileAsBytes("res://project.godot");
        Variant packedByteVariant = new Variant(projectBytes);
        GD.Print("LeanCLR demo: variant packed byte array type = " + packedByteVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: packed byte array wrapper exists = " + (packedByteVariant.AsPackedByteArray() != null).ToString());
        packedByteVariant.Dispose();
        PackedByteArray manualBytes = new PackedByteArray();
        manualBytes.Add(1);
        manualBytes.Add(2);
        manualBytes[1] = 3;
        GD.Print("LeanCLR demo: packed byte manual count = " + manualBytes.Count.ToString());
        GD.Print("LeanCLR demo: packed byte manual second = " + manualBytes[1].ToString());
        manualBytes.Clear();
        GD.Print("LeanCLR demo: packed byte manual cleared = " + manualBytes.Count.ToString());
        manualBytes.Dispose();
        projectBytes.Dispose();
        DirAccess projectDir = DirAccess.Open("res://");
        GD.Print("LeanCLR demo: dir access open = " + (projectDir != null).ToString());
        GD.Print("LeanCLR demo: dir open error = " + DirAccess.GetOpenError().ToString());
        GD.Print("LeanCLR demo: dir drive count >= 0 = " + (DirAccess.GetDriveCount() >= 0).ToString());
        if (projectDir != null)
        {
            projectDir.Dispose();
        }
        PackedStringArray projectFiles = DirAccess.GetFilesAt("res://");
        bool foundProjectFile = false;
        for (int i = 0; i < projectFiles.Count; ++i)
        {
            if (projectFiles[i] == "project.godot")
            {
                foundProjectFile = true;
            }
        }
        GD.Print("LeanCLR demo: packed files count > 0 = " + (projectFiles.Count > 0).ToString());
        GD.Print("LeanCLR demo: packed files include project = " + foundProjectFile.ToString());
        projectFiles.Dispose();
        PackedInt32Array packedInts = new PackedInt32Array();
        packedInts.Add(4);
        packedInts[0] = 5;
        GD.Print("LeanCLR demo: packed int32 first = " + packedInts[0].ToString());
        packedInts.Dispose();
        PackedInt64Array packedLongs = new PackedInt64Array();
        packedLongs.Add(6L);
        GD.Print("LeanCLR demo: packed int64 count = " + packedLongs.Count.ToString());
        packedLongs.Dispose();
        PackedFloat32Array packedFloats = new PackedFloat32Array();
        packedFloats.Add(1.25f);
        GD.Print("LeanCLR demo: packed float32 first = " + packedFloats[0].ToString());
        packedFloats.Dispose();
        PackedFloat64Array packedDoubles = new PackedFloat64Array();
        packedDoubles.Add(2.5);
        GD.Print("LeanCLR demo: packed float64 first = " + packedDoubles[0].ToString());
        packedDoubles.Dispose();
        PackedVector2Array packedVector2s = new PackedVector2Array();
        packedVector2s.Add(new Vector2(1.0f, 2.0f));
        GD.Print("LeanCLR demo: packed vector2 first = " + packedVector2s[0].ToString());
        packedVector2s.Dispose();
        PackedVector3Array packedVector3s = new PackedVector3Array();
        packedVector3s.Add(new Vector3(3.0f, 4.0f, 5.0f));
        GD.Print("LeanCLR demo: packed vector3 first = " + packedVector3s[0].ToString());
        packedVector3s.Dispose();
        PackedColorArray packedColors = new PackedColorArray();
        packedColors.Add(new Color(0.6f, 0.7f, 0.8f, 1.0f));
        GD.Print("LeanCLR demo: packed color first = " + packedColors[0].ToString());
        packedColors.Dispose();
        PackedStringArray csvValues = new PackedStringArray(new string[] { "alpha", "beta" });
        GD.Print("LeanCLR demo: packed manual first = " + csvValues[0]);
        FileAccess csvFile = FileAccess.Open("user://leanclr_packed.csv", FileAccess.ModeFlags.Write);
        bool csvStored = csvFile != null && csvFile.StoreCsvLine(csvValues);
        GD.Print("LeanCLR demo: packed csv stored = " + csvStored.ToString());
        if (csvFile != null)
        {
            csvFile.Dispose();
        }
        csvValues.Dispose();
        Image image = Image.CreateEmpty(4, 4, false, Image.Format.Rgba8);
        image.SetPixel(2, 1, new Color(1.0f, 0.0f, 0.0f, 1.0f));
        GD.Print("LeanCLR demo: image used rect = " + image.GetUsedRect().ToString());
        image.Dispose();
        PhysicsRayQueryParameters3D rayQuery = PhysicsRayQueryParameters3D.Create(new Vector3(1.0f, 2.0f, 3.0f), new Vector3(4.0f, 5.0f, 6.0f));
        GD.Print("LeanCLR demo: physics ray 3d query exists = " + (rayQuery != null).ToString());
        if (rayQuery != null)
        {
            GD.Print("LeanCLR demo: physics ray 3d from = " + rayQuery.GetFrom().ToString());
            GD.Print("LeanCLR demo: physics ray 3d to = " + rayQuery.GetTo().ToString());
            rayQuery.Dispose();
        }
        Node3D node3D = GetNode<Node3D>(new NodePath("Node3DDemo"));
        node3D.SetPosition(new Vector3(7.0f, 8.0f, 9.0f));
        node3D.SetQuaternion(Quaternion.Identity);
        node3D.SetBasis(Basis.Identity);
        node3D.SetTransform(new Transform3D(Basis.Identity, new Vector3(10.0f, 11.0f, 12.0f)));
        GD.Print("LeanCLR demo: node3d position = " + node3D.GetPosition().ToString());
        GD.Print("LeanCLR demo: node3d quaternion = " + node3D.GetQuaternion().ToString());
        GD.Print("LeanCLR demo: node3d basis = " + node3D.GetBasis().ToString());
        GD.Print("LeanCLR demo: node3d transform = " + node3D.GetTransform().ToString());
        CPUParticles3D particles3D = GetNode<CPUParticles3D>(new NodePath("CpuParticles3DDemo"));
        particles3D.SetVisibilityAabb(new Aabb(new Vector3(1.0f, 2.0f, 3.0f), new Vector3(4.0f, 5.0f, 6.0f)));
        GD.Print("LeanCLR demo: particles visibility aabb = " + particles3D.GetVisibilityAabb().ToString());
        Camera3D camera3D = GetNode<Camera3D>(new NodePath("Camera3DDemo"));
        GD.Print("LeanCLR demo: camera transform = " + camera3D.GetCameraTransform().ToString());
        Projection cameraProjection = camera3D.GetCameraProjection();
        GD.Print("LeanCLR demo: camera projection = " + cameraProjection.ToString());
        Variant projectionVariant = new Variant(cameraProjection);
        GD.Print("LeanCLR demo: variant projection type = " + projectionVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant projection = " + projectionVariant.AsProjection().ToString());
        projectionVariant.Dispose();
        Plane demoPlane = new Plane(new Vector3(0.0f, 1.0f, 0.0f), 2.0f);
        Variant planeVariant = new Variant(demoPlane);
        GD.Print("LeanCLR demo: variant plane type = " + planeVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant plane = " + planeVariant.AsPlane().ToString());
        planeVariant.Dispose();
        Sprite2D sprite = GetNode<Sprite2D>(new NodePath("SpriteDemo"));
        Texture2D spriteTexture = sprite.GetTexture();
        sprite.Centered = false;
        sprite.Offset = new Vector2(5.0f, 6.0f);
        sprite.FlipH = true;
        sprite.SetHframes(2);
        sprite.SetVframes(2);
        sprite.SetFrameCoords(new Vector2i(1, 1));
        SetRotationDegrees(15.0f);
        GD.Print("LeanCLR demo: sprite centered = " + sprite.Centered.ToString());
        GD.Print("LeanCLR demo: sprite texture is null = " + (spriteTexture == null).ToString());
        GD.Print("LeanCLR demo: sprite offset = " + sprite.Offset.ToString());
        GD.Print("LeanCLR demo: sprite flip h = " + sprite.FlipH.ToString());
        GD.Print("LeanCLR demo: sprite frame coords = " + sprite.GetFrameCoords().ToString());
        GD.Print("LeanCLR demo: rotation degrees = " + GetRotationDegrees().ToString());
        NodePath childPath = new NodePath("Child");
        Node child = GetNode<Node>(childPath);
        GD.Print("LeanCLR demo: child before QueueFree = " + child.Name);
        GD.Print("LeanCLR demo: child parent = " + child.GetParent().Name);
        GD.Print("LeanCLR demo: child count = " + GetChildCount().ToString());
        GD.Print("LeanCLR demo: inside tree = " + IsInsideTree().ToString());
        GD.Print("LeanCLR demo: tree node count > 0 = " + (GetTree().GetNodeCount() > 0).ToString());
        SetProcessMode(Node.ProcessMode.Always);
        GD.Print("LeanCLR demo: process mode = " + GetProcessMode().ToString());
        Variant selfVariant = new Variant(this);
        Node2D selfObject = selfVariant.AsObject<Node2D>();
        GD.Print("LeanCLR demo: variant object name = " + selfObject.Name.ToString());
        selfVariant.Dispose();
        Variant vector2Variant = new Variant(new Vector2(3.0f, 4.0f));
        GD.Print("LeanCLR demo: variant vector2 = " + vector2Variant.AsVector2().ToString());
        GD.Print("LeanCLR demo: variant vector2 stringify = " + vector2Variant.ToString());
        vector2Variant.Dispose();
        Variant vector3Variant = new Variant(new Vector3(5.0f, 6.0f, 7.0f));
        GD.Print("LeanCLR demo: variant vector3 = " + vector3Variant.AsVector3().ToString());
        vector3Variant.Dispose();
        Variant stringNameVariant = new Variant(new StringName("leanclr_name"));
        GD.Print("LeanCLR demo: variant string name type = " + stringNameVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant string name = " + stringNameVariant.AsStringName().ToString());
        stringNameVariant.Dispose();
        Variant nodePathVariant = new Variant(new NodePath("Child"));
        GD.Print("LeanCLR demo: variant node path type = " + nodePathVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant node path = " + nodePathVariant.AsNodePath().ToString());
        nodePathVariant.Dispose();
        Variant ridVariant = new Variant(new RID(0));
        GD.Print("LeanCLR demo: variant rid type = " + ridVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant rid valid = " + ridVariant.AsRID().IsValid().ToString());
        ridVariant.Dispose();
        PackedStringArray packedStrings = new PackedStringArray(new string[] { "alpha", "beta" });
        Variant packedStringArrayVariant = new Variant(packedStrings);
        PackedStringArray packedStringsRoundtrip = packedStringArrayVariant.AsPackedStringArray();
        GD.Print("LeanCLR demo: variant packed string array type = " + packedStringArrayVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: packed string array count = " + packedStringsRoundtrip.Count.ToString());
        GD.Print("LeanCLR demo: packed string array first = " + packedStringsRoundtrip[0]);
        packedStringsRoundtrip.Dispose();
        packedStringArrayVariant.Dispose();
        packedStrings.Dispose();
        Array demoArray = new Array();
        demoArray.Add(new Variant("array first"));
        demoArray.Add(new Variant(new Vector2(8.0f, 9.0f)));
        Variant arrayVariant = new Variant(demoArray);
        GD.Print("LeanCLR demo: variant array type = " + arrayVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant array wrapper exists = " + (arrayVariant.AsArray() != null).ToString());
        GD.Print("LeanCLR demo: array count = " + demoArray.Count.ToString());
        GD.Print("LeanCLR demo: array first = " + demoArray[0].ToString());
        GD.Print("LeanCLR demo: array second = " + demoArray[1].AsVector2().ToString());
        Variant arrayInserted = new Variant("array inserted");
        demoArray.Insert(1, arrayInserted);
        GD.Print("LeanCLR demo: array inserted = " + demoArray[1].ToString());
        GD.Print("LeanCLR demo: array contains inserted = " + demoArray.Contains(arrayInserted).ToString());
        GD.Print("LeanCLR demo: array inserted index = " + demoArray.IndexOf(arrayInserted).ToString());
        int arrayEnumerated = 0;
        foreach (Variant item in demoArray)
        {
            arrayEnumerated++;
        }
        GD.Print("LeanCLR demo: array enumerated = " + arrayEnumerated.ToString());
        demoArray.RemoveAt(1);
        GD.Print("LeanCLR demo: array count after remove = " + demoArray.Count.ToString());
        demoArray.Clear();
        GD.Print("LeanCLR demo: array count after clear = " + demoArray.Count.ToString());
        arrayInserted.Dispose();
        arrayVariant.Dispose();
        demoArray.Dispose();
        Dictionary demoDictionary = new Dictionary();
        Variant dictionaryKey = new Variant("answer");
        demoDictionary[dictionaryKey] = new Variant(42);
        Variant dictionaryVariant = new Variant(demoDictionary);
        GD.Print("LeanCLR demo: variant dictionary type = " + dictionaryVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant dictionary wrapper exists = " + (dictionaryVariant.AsDictionary() != null).ToString());
        GD.Print("LeanCLR demo: dictionary count = " + demoDictionary.Count.ToString());
        GD.Print("LeanCLR demo: dictionary has key = " + demoDictionary.ContainsKey(dictionaryKey).ToString());
        Variant dictionaryValue = demoDictionary[dictionaryKey];
        GD.Print("LeanCLR demo: dictionary value type = " + dictionaryValue.VariantType.ToString());
        GD.Print("LeanCLR demo: dictionary value = " + dictionaryValue.ToString());
        GD.Print("LeanCLR demo: dictionary value int = " + dictionaryValue.AsInt64().ToString());
        Array dictionaryKeys = demoDictionary.Keys;
        Array dictionaryValues = demoDictionary.Values;
        GD.Print("LeanCLR demo: dictionary keys count = " + dictionaryKeys.Count.ToString());
        GD.Print("LeanCLR demo: dictionary values first = " + dictionaryValues[0].ToString());
        int dictionaryEnumerated = 0;
        foreach (var entry in demoDictionary)
        {
            if (entry.Key.ToString() == "answer" && entry.Value.AsInt64() == 42)
            {
                dictionaryEnumerated++;
            }
        }
        GD.Print("LeanCLR demo: dictionary enumerated = " + dictionaryEnumerated.ToString());
        GD.Print("LeanCLR demo: dictionary removed = " + demoDictionary.Remove(dictionaryKey).ToString());
        GD.Print("LeanCLR demo: dictionary count after remove = " + demoDictionary.Count.ToString());
        demoDictionary[dictionaryKey] = new Variant(7);
        demoDictionary.Clear();
        GD.Print("LeanCLR demo: dictionary count after clear = " + demoDictionary.Count.ToString());
        dictionaryKeys.Dispose();
        dictionaryValues.Dispose();
        dictionaryValue.Dispose();
        dictionaryKey.Dispose();
        dictionaryVariant.Dispose();
        demoDictionary.Dispose();
        Callable setMetaCallable = new Callable(this, new StringName("set_meta"));
        Variant callableMetaKey = new Variant("leanclr_callable_meta");
        Variant callableMetaValue = new Variant("LeanCLR Callable Variant");
        setMetaCallable.Call(callableMetaKey, callableMetaValue).Dispose();
        Variant callableMetaRoundtrip = GetMeta(new StringName("leanclr_callable_meta"));
        GD.Print("LeanCLR demo: callable valid = " + setMetaCallable.IsValid().ToString());
        GD.Print("LeanCLR demo: callable method = " + setMetaCallable.GetMethod().ToString());
        GD.Print("LeanCLR demo: callable call meta = " + callableMetaRoundtrip.ToString());
        callableMetaRoundtrip.Dispose();
        callableMetaValue.Dispose();
        callableMetaKey.Dispose();
        AddUserSignal("leanclr_user_signal");
        Signal userSignal = new Signal(this, new StringName("leanclr_user_signal"));
        Variant signalMetaKey = new Variant("leanclr_signal_meta");
        Variant signalMetaValue = new Variant("LeanCLR Signal Variant");
        Callable signalCallable = setMetaCallable.Bind(signalMetaKey, signalMetaValue);
        GD.Print("LeanCLR demo: signal name = " + userSignal.GetName().ToString());
        GD.Print("LeanCLR demo: signal connect = " + userSignal.Connect(signalCallable, 0).ToString());
        userSignal.Emit();
        Variant signalMetaRoundtrip = GetMeta(new StringName("leanclr_signal_meta"));
        GD.Print("LeanCLR demo: signal emitted meta = " + signalMetaRoundtrip.ToString());
        Variant callableVariant = new Variant(signalCallable);
        Variant signalVariant = new Variant(userSignal);
        GD.Print("LeanCLR demo: variant callable type = " + callableVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant callable valid = " + callableVariant.AsCallable().IsValid().ToString());
        GD.Print("LeanCLR demo: variant signal type = " + signalVariant.VariantType.ToString());
        GD.Print("LeanCLR demo: variant signal name = " + signalVariant.AsSignal().GetName().ToString());
        AddUserSignal("leanclr_managed_signal");
        Signal managedSignal = new Signal(this, new StringName("leanclr_managed_signal"));
        Callable managedCallable = new Callable(this, new StringName("OnLeanClrManagedSignal"));
        GD.Print("LeanCLR demo: managed callable valid = " + managedCallable.IsValid().ToString());
        GD.Print("LeanCLR demo: managed signal connect = " + managedSignal.Connect(managedCallable, 0).ToString());
        managedSignal.Emit();
        Variant managedSignalRoundtrip = GetMeta(new StringName("leanclr_managed_signal_meta"));
        GD.Print("LeanCLR demo: managed signal emitted meta = " + managedSignalRoundtrip.ToString());
        managedSignalRoundtrip.Dispose();
        AddUserSignal("leanclr_managed_arg_signal");
        Signal managedArgSignal = new Signal(this, new StringName("leanclr_managed_arg_signal"));
        Callable managedArgCallable = new Callable(this, new StringName("OnLeanClrManagedSignalWithArg"));
        GD.Print("LeanCLR demo: managed arg callable valid = " + managedArgCallable.IsValid().ToString());
        GD.Print("LeanCLR demo: managed arg signal connect = " + managedArgSignal.Connect(managedArgCallable, 0).ToString());
        Variant managedArgPayload = new Variant("LeanCLR Managed Signal Payload");
        managedArgSignal.Emit(managedArgPayload);
        Variant managedArgSignalRoundtrip = GetMeta(new StringName("leanclr_managed_arg_signal_meta"));
        GD.Print("LeanCLR demo: managed arg signal emitted meta = " + managedArgSignalRoundtrip.ToString());
        managedArgSignalRoundtrip.Dispose();
        AddUserSignal("leanclr_managed_multi_signal");
        Signal managedMultiSignal = new Signal(this, new StringName("leanclr_managed_multi_signal"));
        Callable managedMultiCallable = new Callable(this, new StringName("OnLeanClrManagedSignalWithArgs"));
        GD.Print("LeanCLR demo: managed multi callable valid = " + managedMultiCallable.IsValid().ToString());
        GD.Print("LeanCLR demo: managed multi signal connect = " + managedMultiSignal.Connect(managedMultiCallable, 0).ToString());
        Variant managedMultiFirst = new Variant("LeanCLR");
        Variant managedMultiSecond = new Variant("Multi Signal Payload");
        managedMultiSignal.Emit(managedMultiFirst, managedMultiSecond);
        Variant managedMultiSignalRoundtrip = GetMeta(new StringName("leanclr_managed_multi_signal_meta"));
        GD.Print("LeanCLR demo: managed multi signal emitted meta = " + managedMultiSignalRoundtrip.ToString());
        managedMultiSignalRoundtrip.Dispose();
        Callable typedCallable = new Callable(this, new StringName("OnLeanClrTypedCallable"));
        Variant typedCallResult = typedCallable.Call(new Variant("LeanCLR Typed"), new Variant(41), new Variant(1.5), new Variant(new Vector2(2.0f, 3.0f)), new Variant(this));
        GD.Print("LeanCLR demo: typed callable result = " + typedCallResult.ToString());
        typedCallResult.Dispose();
        Callable returnIntCallable = new Callable(this, new StringName("OnLeanClrReturnInt"));
        Variant returnIntResult = returnIntCallable.Call(new Variant(41));
        GD.Print("LeanCLR demo: return int callable result = " + returnIntResult.ToString());
        returnIntResult.Dispose();
        returnIntCallable.Dispose();
        Callable structCallable = new Callable(this, new StringName("OnLeanClrStructCallable"));
        Variant structCallResult = structCallable.Call(new Variant(new StringName("struct_name")), new Variant(new NodePath("Child")), new Variant(new RID(0)), new Variant(new Color(0.1f, 0.2f, 0.3f, 1.0f)), new Variant(Quaternion.Identity), new Variant(Basis.Identity), new Variant(Transform3D.Identity));
        GD.Print("LeanCLR demo: struct callable result = " + structCallResult.ToString());
        structCallResult.Dispose();
        structCallable.Dispose();
        Callable returnColorCallable = new Callable(this, new StringName("OnLeanClrReturnColor"));
        Variant returnColorResult = returnColorCallable.Call(new Variant(new Color(0.2f, 0.3f, 0.4f, 1.0f)));
        GD.Print("LeanCLR demo: return color callable result = " + returnColorResult.AsColor().ToString());
        returnColorResult.Dispose();
        returnColorCallable.Dispose();
        int delegateSignalCount = 0;
        Callable delegateCallable = Callable.From(() => { delegateSignalCount = 42; });
        AddUserSignal("leanclr_delegate_signal");
        Signal delegateSignal = new Signal(this, new StringName("leanclr_delegate_signal"));
        GD.Print("LeanCLR demo: delegate callable valid = " + delegateCallable.IsValid().ToString());
        GD.Print("LeanCLR demo: delegate signal connect = " + delegateSignal.Connect(delegateCallable, 0).ToString());
        delegateSignal.Emit();
        GD.Print("LeanCLR demo: delegate signal count = " + delegateSignalCount.ToString());
        Callable delegateArgCallable = Callable.From<Variant>((payload) => { SetMeta(new StringName("leanclr_delegate_arg_meta"), payload); });
        AddUserSignal("leanclr_delegate_arg_signal");
        Signal delegateArgSignal = new Signal(this, new StringName("leanclr_delegate_arg_signal"));
        GD.Print("LeanCLR demo: delegate arg signal connect = " + delegateArgSignal.Connect(delegateArgCallable, 0).ToString());
        delegateArgSignal.Emit(new Variant("LeanCLR Delegate Payload"));
        Variant delegateArgRoundtrip = GetMeta(new StringName("leanclr_delegate_arg_meta"));
        GD.Print("LeanCLR demo: delegate arg meta = " + delegateArgRoundtrip.ToString());
        delegateArgRoundtrip.Dispose();
        delegateArgCallable.Dispose();
        delegateArgSignal.Dispose();
        delegateCallable.Dispose();
        delegateSignal.Emit();
        GD.Print("LeanCLR demo: delegate signal count after dispose = " + delegateSignalCount.ToString());
        delegateSignal.Dispose();
        typedCallable.Dispose();
        managedMultiSecond.Dispose();
        managedMultiFirst.Dispose();
        managedMultiCallable.Dispose();
        managedMultiSignal.Dispose();
        managedArgPayload.Dispose();
        managedArgCallable.Dispose();
        managedArgSignal.Dispose();
        managedCallable.Dispose();
        managedSignal.Dispose();
        callableVariant.Dispose();
        signalVariant.Dispose();
        signalMetaRoundtrip.Dispose();
        signalMetaValue.Dispose();
        signalMetaKey.Dispose();
        signalCallable.Dispose();
        userSignal.Dispose();
        setMetaCallable.Dispose();
        SetPhysicsProcess(true);
        SetProcessInput(true);
        Call(new StringName("_input"), new Variant((GodotObject)null)).Dispose();
        Call(new StringName("_gui_input"), new Variant((GodotObject)null)).Dispose();
        child.QueueFree();
    }

    public void OnLeanClrManagedSignal()
    {
        SetMeta(new StringName("leanclr_managed_signal_meta"), new Variant("LeanCLR Managed Signal Variant"));
    }

    public void OnLeanClrManagedSignalWithArg(Variant payload)
    {
        SetMeta(new StringName("leanclr_managed_arg_signal_meta"), payload);
    }

    public void OnLeanClrManagedSignalWithArgs(Variant[] payloads)
    {
        SetMeta(new StringName("leanclr_managed_multi_signal_meta"), new Variant(payloads[0].ToString() + " " + payloads[1].ToString()));
    }

    public string OnLeanClrTypedCallable(string label, int count, double amount, Vector2 point, Node node)
    {
        return label + " " + (count + 1).ToString() + " " + amount.ToString() + " " + point.ToString() + " " + node.Name.ToString();
    }

    public int OnLeanClrReturnInt(int value)
    {
        return value + 1;
    }

    public string OnLeanClrStructCallable(StringName name, NodePath path, RID rid, Color color, Quaternion quaternion, Basis basis, Transform3D transform)
    {
        return name.ToString() + " " + path.ToString() + " " + rid.IsValid().ToString() + " " + color.ToString() + " " + quaternion.ToString() + " " + basis.ToString() + " " + transform.ToString();
    }

    public Color OnLeanClrReturnColor(Color value)
    {
        return value;
    }

    public override void _Process(double delta)
    {
        if (processPrinted)
        {
            return;
        }

        processPrinted = true;
        GD.Print("LeanCLR demo: _Process delta > 0 = " + (delta > 0.0).ToString());
    }

    public override void _PhysicsProcess(float delta)
    {
        if (physicsProcessPrinted)
        {
            return;
        }

        physicsProcessPrinted = true;
        GD.Print("LeanCLR demo: _PhysicsProcess delta > 0 = " + (delta > 0.0f).ToString());
    }

    public override void _Input(InputEvent event_)
    {
        if (inputPrinted)
        {
            return;
        }

        inputPrinted = true;
        GD.Print("LeanCLR demo: _Input event wrapper exists = " + (event_ != null).ToString());
    }

    public void _GuiInput(InputEvent event_)
    {
        if (guiInputPrinted)
        {
            return;
        }

        guiInputPrinted = true;
        GD.Print("LeanCLR demo: _GuiInput event wrapper exists = " + (event_ != null).ToString());
    }
}
