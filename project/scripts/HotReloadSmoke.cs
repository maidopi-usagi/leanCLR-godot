using Godot;

namespace Game;

public partial class HotReloadSmoke : Node
{
	private const string Version = "flappy-physics-v1";
	private const float WorldWidth = 540.0f;
	private const float WorldHeight = 360.0f;
	private const float GroundY = 320.0f;
	private const float BirdX = 108.0f;
	private const float BirdSize = 40.0f;
	private const float Gravity = 960.0f;
	private const float FlapVelocity = -330.0f;
	private const float PipeSpeed = 170.0f;
	private const float PipeWidth = 60.0f;
	private const float GapHeight = 160.0f;
	private const float ResetPipeX = 560.0f;
	private const float PipeRecycleX = -80.0f;
	private const int MinGapCenter = 118;
	private const int MaxGapCenter = 235;
	private static readonly Color AliveBirdColor = new Color(1.0f, 0.95f, 0.18f, 1.0f);
	private static readonly Color GameOverBirdColor = new Color(1.0f, 0.32f, 0.22f, 1.0f);

	[Export(PropertyHint.Range, "1,10,1")]
	public int FlapPower { get; set; } = 5;

	private float elapsed;
	private float birdY;
	private float velocityY;
	private float pipeX;
	private int gapCenter;
	private int score;
	private bool gameOver;
	private bool passedPipe;
	private bool processLogged;
	private bool runtimeReloadedObject;

	public override void _Ready()
	{
		if (birdY <= 0.0f || pipeX <= 0.0f)
		{
			ResetGame();
		}
		ApplyGameState();
		GD.Print("LeanCLR flappy reload: version = " + Version);
		GD.Print("LeanCLR flappy reload: score = " + score.ToString());
		GD.Print("LeanCLR flappy reload: bird y = " + ((int)birdY).ToString());
		GD.Print("LeanCLR flappy reload: velocity y = " + ((int)velocityY).ToString());
		GD.Print("LeanCLR flappy reload: active marker = " + FileAccess.GetFileAsString("res://leanclr/live_reload.txt").Trim());
	}

	public override void _Input(InputEvent event_)
	{
		if (!IsGameplayObjectActive())
		{
			return;
		}

		if (event_ != null && event_.IsPressed() && !event_.IsEcho())
		{
			ForceFlap();
		}
	}

	public void ForceFlap()
	{
		if (gameOver)
		{
			ResetGame();
			GD.Print("LeanCLR flappy input: restart");
			return;
		}

		velocityY = FlapVelocity - FlapPower * 10.0f;
		GD.Print("LeanCLR flappy input: flap velocity = " + ((int)velocityY).ToString());
	}

	public Variant CaptureHotReloadState()
	{
		Dictionary state = new Dictionary();
		state[new Variant("elapsed")] = new Variant(elapsed);
		state[new Variant("birdY")] = new Variant(birdY);
		state[new Variant("velocityY")] = new Variant(velocityY);
		state[new Variant("pipeX")] = new Variant(pipeX);
		state[new Variant("gapCenter")] = new Variant(gapCenter);
		state[new Variant("score")] = new Variant(score);
		state[new Variant("gameOver")] = new Variant(gameOver);
		state[new Variant("passedPipe")] = new Variant(passedPipe);
		state[new Variant("processLogged")] = new Variant(processLogged);
		GD.Print("LeanCLR hot reload state: captured score = " + score.ToString() + " y = " + ((int)birdY).ToString());
		return new Variant(state);
	}

	public void RestoreHotReloadState(Variant stateVariant)
	{
		runtimeReloadedObject = true;
		Dictionary state = stateVariant.AsDictionary();
		if (state != null)
		{
			elapsed = ReadFloat(state, "elapsed", elapsed);
			birdY = ReadFloat(state, "birdY", birdY);
			velocityY = ReadFloat(state, "velocityY", velocityY);
			pipeX = ReadFloat(state, "pipeX", pipeX);
			gapCenter = ReadInt(state, "gapCenter", gapCenter);
			score = ReadInt(state, "score", score);
			gameOver = ReadBool(state, "gameOver", gameOver);
			passedPipe = ReadBool(state, "passedPipe", passedPipe);
			processLogged = ReadBool(state, "processLogged", processLogged);
		}
		GD.Print("LeanCLR hot reload state: restored score = " + score.ToString() + " y = " + ((int)birdY).ToString());
	}

	public void OnHotReloaded()
	{
		runtimeReloadedObject = true;
		ApplyGameState();
		GD.Print("LeanCLR hot reload state: active score after reload = " + score.ToString() + " y = " + ((int)birdY).ToString());
	}

	public override void _Process(double delta)
	{
		if (!IsGameplayObjectActive())
		{
			return;
		}

		float dt = Clamp((float)delta, 0.0f, 0.033f);
		elapsed += dt;

		if (!gameOver)
		{
			velocityY += Gravity * dt;
			birdY += velocityY * dt;
			pipeX -= PipeSpeed * dt;

			if (pipeX < PipeRecycleX)
			{
				pipeX = ResetPipeX;
				gapCenter = NextGapCenter();
				passedPipe = false;
			}

			if (!passedPipe && pipeX + PipeWidth < BirdX)
			{
				passedPipe = true;
				score++;
				GD.Print("LeanCLR flappy score: " + score.ToString());
			}

			if (CheckCollision())
			{
				gameOver = true;
				GD.Print("LeanCLR flappy collision: game over score = " + score.ToString());
			}
		}

		ApplyGameState();
		if (!processLogged)
		{
			processLogged = true;
			GD.Print("LeanCLR flappy process: playable physics tick delta = " + delta.ToString());
		}
	}

	private void ResetGame()
	{
		elapsed = 0.0f;
		birdY = 146.0f;
		velocityY = 0.0f;
		pipeX = 420.0f;
		gapCenter = 172;
		score = 0;
		gameOver = false;
		passedPipe = false;
		processLogged = false;
	}

	private bool CheckCollision()
	{
		if (birdY < 0.0f || birdY + BirdSize > GroundY)
		{
			return true;
		}

		bool overlapsPipeX = BirdX + BirdSize > pipeX && BirdX < pipeX + PipeWidth;
		if (!overlapsPipeX)
		{
			return false;
		}

		float gapTop = gapCenter - GapHeight * 0.5f;
		float gapBottom = gapCenter + GapHeight * 0.5f;
		return birdY < gapTop || birdY + BirdSize > gapBottom;
	}

	private void ApplyGameState()
	{
		TextureRect bird = GetNodeOrNull<TextureRect>("../GameWorld/Bird");
		ColorRect pipeTop = GetNodeOrNull<ColorRect>("../GameWorld/PipeTop");
		ColorRect pipeBottom = GetNodeOrNull<ColorRect>("../GameWorld/PipeBottom");
		Label title = GetNodeOrNull<Label>("../GameWorld/Hud/Title");
		Label status = GetNodeOrNull<Label>("../GameWorld/Hud/DemoStatus");

		if (bird != null)
		{
			bird.Position = new Vector2(BirdX, birdY);
			bird.Size = new Vector2(BirdSize, BirdSize);
			bird.SetModulate(gameOver ? GameOverBirdColor : AliveBirdColor);
			bird.SetRotationDegrees(Clamp(velocityY / 18.0f, -24.0f, 58.0f));
		}

		float gapTop = gapCenter - GapHeight * 0.5f;
		float gapBottom = gapCenter + GapHeight * 0.5f;
		if (pipeTop != null)
		{
			pipeTop.Position = new Vector2(pipeX, 0.0f);
			pipeTop.Size = new Vector2(PipeWidth, gapTop);
		}
		if (pipeBottom != null)
		{
			pipeBottom.Position = new Vector2(pipeX, gapBottom);
			pipeBottom.Size = new Vector2(PipeWidth, GroundY - gapBottom);
		}

		if (title != null)
		{
			title.Text = gameOver ? "Game Over - press any key/click to restart" : "Flap: any key or mouse click";
		}
		if (status != null)
		{
			status.Text = "Running " + Version + " | score=" + score.ToString() + " | y=" + ((int)birdY).ToString() + " | vy=" + ((int)velocityY).ToString() + " | pipeX=" + ((int)pipeX).ToString();
		}
	}

	private int NextGapCenter()
	{
		int cycle = ((score * 47) + 31) % (MaxGapCenter - MinGapCenter);
		return MinGapCenter + cycle;
	}

	private bool IsGameplayObjectActive()
	{
		string marker = FileAccess.GetFileAsString("res://leanclr/live_reload.txt").Trim();
		return marker == "Game" || runtimeReloadedObject;
	}

	private float ReadFloat(Dictionary state, string key, float fallback)
	{
		Variant variantKey = new Variant(key);
		return state.ContainsKey(variantKey) ? (float)state[variantKey].AsDouble() : fallback;
	}

	private int ReadInt(Dictionary state, string key, int fallback)
	{
		Variant variantKey = new Variant(key);
		return state.ContainsKey(variantKey) ? (int)state[variantKey].AsInt64() : fallback;
	}

	private bool ReadBool(Dictionary state, string key, bool fallback)
	{
		Variant variantKey = new Variant(key);
		return state.ContainsKey(variantKey) ? state[variantKey].AsBool() : fallback;
	}

	private float Clamp(float value, float min, float max)
	{
		return value < min ? min : (value > max ? max : value);
	}
}
