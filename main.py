from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")

rooms = {}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/game/{room_id}")
def game_page(request: Request, room_id: str):
    return templates.TemplateResponse(
        request,
        "game.html",
        {"room_id": room_id}
    )


def check_winner(board):
    wins = [
        [0,1,2], [3,4,5], [6,7,8],
        [0,3,6], [1,4,7], [2,5,8],
        [0,4,8], [2,4,6]
    ]

    for a, b, c in wins:
        if board[a] != "" and board[a] == board[b] == board[c]:
            return board[a]

    if "" not in board:
        return "draw"

    return None


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()

    if room_id not in rooms:
        rooms[room_id] = {
            "players": [],
            "board": [""] * 9,
            "turn": "O",
            "game_over": False
        }

    room = rooms[room_id]

    if len(room["players"]) >= 2:
        await websocket.send_text(json.dumps({"type": "full"}))
        await websocket.close()
        return

    symbol = "O" if len(room["players"]) == 0 else "X"
    room["players"].append((websocket, symbol))

    await websocket.send_text(json.dumps({
        "type": "joined",
        "symbol": symbol
    }))

    if len(room["players"]) == 2:
        for player, sym in room["players"]:
            await player.send_text(json.dumps({
                "type": "start",
                "turn": "Your turn" if sym == room["turn"] else "Wait"
            }))

    try:
        while True:
            data = await websocket.receive_text()

            if room["game_over"]:
                continue

            move = int(data)

            player_symbol = None
            for ws, sym in room["players"]:
                if ws == websocket:
                    player_symbol = sym

            if player_symbol != room["turn"]:
                await websocket.send_text(json.dumps({
                    "type": "wait"
                }))
                continue

            if room["board"][move] != "":
                continue

            room["board"][move] = player_symbol

            for player, _ in room["players"]:
                await player.send_text(json.dumps({
                    "type": "move",
                    "index": move,
                    "symbol": player_symbol
                }))

            winner = check_winner(room["board"])

            if winner:
                room["game_over"] = True

                for player, sym in room["players"]:
                    if winner == "draw":
                        msg_type = "draw"
                    elif sym == winner:
                        msg_type = "win"
                    else:
                        msg_type = "lose"

                    await player.send_text(json.dumps({
                        "type": msg_type
                    }))
                
                room[room_id].clear()
                return

            room["turn"] = "X" if room["turn"] == "O" else "O"

            for player, sym in room["players"]:
                await player.send_text(json.dumps({
                    "type": "turn",
                    "turn": "Your turn" if sym == room["turn"] else "Wait"
                }))

    except WebSocketDisconnect:
        room["players"] = [
            p for p in room["players"] if p[0] != websocket
        ]

        if room["players"]:
            for player, _ in room["players"]:
                await player.send_text(json.dumps({
                    "type": "opponent_left"
                }))
        else:
            del rooms[room_id]