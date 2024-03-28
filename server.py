
import asyncio
import websockets

# 보드 초기화
BOARD_SIZE = 20
WIN_CONDITION = 4  # 승리 조건 (연속된 돌의 개수)
MAX_PLAYERS = 4  # 최대 플레이어 수
board = [[' ' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
players = ['＠', '●', '○', '★', 'C','D','E','F','G']
player_conns = []
spectator = []
current_player = 0
game_started = Fals
nicknames = []

# 승자 확인 함수
def check_winner(x, y, player):
    # 가로 확인
    count = 0
    for i in range(BOARD_SIZE):
        if board[y][i] == player:
            count += 1
            if count == WIN_CONDITION:
                return True
        else:
            count = 0

    # 세로 확인
    count = 0
    for i in range(BOARD_SIZE):
        if board[i][x] == player:
            count += 1
            if count == WIN_CONDITION:
                return True
        else:
            count = 0

    # 대각선 확인 (왼쪽 위 -> 오른쪽 아래)
    count = 0
    i, j = y, x
    while i >= 0 and j >= 0:
        i -= 1
        j -= 1
    i += 1
    j += 1
    while i < BOARD_SIZE and j < BOARD_SIZE:
        if board[i][j] == player:
            count += 1
            if count == WIN_CONDITION:
                return True
        else:
            count = 0
        i += 1
        j += 1

    # 대각선 확인 (오른쪽 위 -> 왼쪽 아래)
    count = 0
    i, j = y, x
    while i >= 0 and j < BOARD_SIZE:
        i -= 1
        j += 1
    i += 1
    j -= 1
    while i < BOARD_SIZE and j >= 0:
        if board[i][j] == player:
            count += 1
            if count == WIN_CONDITION:
                return True
        else:
            count = 0
        i += 1
        j -= 1

    return False


# 게임 진행 함수
async def handle_game():
    global current_player, game_started
    
    game_started = True
    while True:
        # 모든 클라이언트에게 보드 상태와 플레이어 정보 전송
        await broadcast(board_msg())

        # 현재 플레이어에게 차례 알림
        await send(player_conns[current_player], "YOUR_TURN")

        # 클라이언트로부터 메시지 수신
        try:
            move = await player_conns[current_player].recv()
        except websockets.exceptions.ConnectionClosed:
            await player_out(player_conns[current_player])
            break

        # 움직임 처리
        x, y = map(int, move.split(','))
        if board[y][x] == ' ':
            board[y][x] = players[current_player]
            if check_winner(x, y, players[current_player]):
                winner = players[current_player]
                board_str = '\n'.join([''.join(row) for row in board])
                await broadcast(f"BOARD|{board_str}")
                await broadcast(f"WINNER|{winner}")
                break
            current_player = (current_player + 1) % MAX_PLAYERS
        else:
            await send(player_conns[current_player],"OCCUPIED")

# 클라이언트 연결 처리 코루틴
async def handle_client(websocket, path):
    global game_started
    if len(player_conns) < MAX_PLAYERS:
        nickname = await websocket.recv()
        player_conns.append(websocket)
        nicknames.append(nickname)
        print(f"{nickname}({websocket.remote_address}) 연결됨")
        await send(websocket,f"TITLE|{MAX_PLAYERS}인{WIN_CONDITION}목")
        if len(player_conns) == MAX_PLAYERS:
            await broadcast("START_GAME")
            await handle_game()
        else:
            await send(websocket,"WAITING")
    else:
        await send(websocket,"GAME_FULL")
        await send(websocket,board_msg())
        spectator.append(websocket)
    
    player_list = '\n'.join([f"{players[i]} : {nicknames[i]}" for i in range(len(player_conns))])
    await broadcast(f"PLAYERS|{player_list}")

    try:
        await websocket.wait_closed()
        await player_out(websocket)

    except websockets.exceptions.ConnectionClosed:
        await player_out(websocket)


    finally:
        if websocket in player_conns:
            player_conns.remove(websocket)
        if len(player_conns) == 0:
            game_started = False

# 메시지 브로드캐스트 함수
async def broadcast(message):
    for conn in player_conns:
        await send(conn, message)
    for conn in spectator:
        await send(conn, message)


async def send(socket, message):
    try:
        await socket.send(message)
    except websockets.exceptions.ConnectionClosed:
        await player_out(socket)

def board_msg():
    board_str = '\n'.join([''.join(row) for row in board])
    player_list = '\n'.join([f"{players[i]} : {nicknames[i]}" for i in range(len(player_conns))])
    message = f"BOARD|{board_str}@PLAYERS|{player_list}@CURRENT_PLAYER|{nicknames[current_player]}"
    return message



async def player_out(socket):
    if socket in player_conns:
        i = player_conns.index(socket) 
        nick = nicknames[i]
        print(f"플레이어 연결이 종료되었습니다: {nick} {socket.remote_address}")
        player_conns.remove(socket)      
        
        await broadcast(f"MSG|{nick}님이 나가서 게임이 터졌습니다. 모두 새로고침 해주세요.")
        await reset_game()
    elif socket in spectator:
        print(f"관전자 연결이 종료되었습니다: {socket.remote_address}")
        spectator.remove(socket)

async def reset_game():
    global board, current_player, game_started,player_conns,spectator,nicknames
    board = [[' ' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    current_player = 0
    game_started = False
    current_player = 0
    game_started = False
    for conn in spectator:
        await conn.close()
    spectator = []
    for conn in player_conns:
        await conn.close()
    player_conns = []
    nicknames = []
# 서버 시작
start_server = websockets.serve(handle_client, '0.0.0.0', 8880)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()